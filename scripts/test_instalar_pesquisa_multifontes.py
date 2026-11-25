"""Testes offline da instalação de pesquisa em KnowledgeStart local personalizado."""
import importlib.util
from pathlib import Path
import unittest

SCRIPTS=Path(__file__).resolve().parent
module_path=SCRIPTS/"instalar_pesquisa_multifontes.py"
spec=importlib.util.spec_from_file_location("knowledge_multifontes_installer",module_path)
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class LocalUICompatibilityTests(unittest.TestCase):
    def test_preserves_customized_page_and_inserts_search_first(self):
        original=(
            '// arquivo personalizado do Codespaces\n'
            'import React from "react";\n'
            'export default function KnowledgeStart({project,onProjectChanged}) {\n'
            ' const saveLocally=()=>42;\n'
            ' return (\n'
            '  <main className="custom-knowledge">\n'
            '    <h2>Minha tela local</h2>\n'
            '    <input aria-label="Tema municipal personalizado" />\n'
            '    <button onClick={saveLocally}>Gravar</button>\n'
            '  </main>\n'
            ' );\n}\n').encode()
        result=installer.adapt_parent(original)
        text=result.decode()
        self.assertIn("BI_KNOWLEDGE_OFFICIAL_SLOT",text)
        self.assertIn("<OfficialKnowledgeSearch project={project}/>",text)
        self.assertIn("Minha tela local",text)
        self.assertIn('aria-label="Tema municipal personalizado"',text)
        self.assertIn("const saveLocally=()=>42",text)
        self.assertTrue(text.index("<OfficialKnowledgeSearch")<text.index("Minha tela local"))
        self.assertEqual(installer.adapt_parent(result),result)
        clean=text.replace('import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";\n','',1)
        clean=clean.replace(
            '\n  {/* BI_KNOWLEDGE_OFFICIAL_SLOT: pesquisa por tema, preserva tela local */}\n'
            '  <OfficialKnowledgeSearch project={project}/>\n','',1)
        self.assertEqual(clean.encode(),original,"Conteúdo local deve ser reversível sem perda.")

    def test_existing_official_slot_does_not_duplicate(self):
        code=('import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";\n'
              'function KnowledgeStart({project}){return <div>'
              '{/* BI_KNOWLEDGE_OFFICIAL_SLOT */}'
              '<OfficialKnowledgeSearch project={project}/>'
              '</div>;}').encode()
        self.assertEqual(installer.adapt_parent(code),code)

    def test_other_layout_with_fragment_root(self):
        code=("import React from 'react';\n"
              "function KnowledgeStart({project}) {\n"
              " return <><h2>Meu projeto</h2></>;\n"
              "}\n").encode()
        result=installer.adapt_parent(code).decode()
        self.assertIn("return <>\n  {/* BI_KNOWLEDGE_OFFICIAL_SLOT",result)
        self.assertIn("<h2>Meu projeto</h2>",result)

    def test_component_with_import_but_without_slot(self):
        code=('import React from "react";\n'
              'import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";\n'
              'function KnowledgeStart({project}){return <div>Minha lista</div>;}').encode()
        result=installer.adapt_parent(code).decode()
        self.assertEqual(result.count('import OfficialKnowledgeSearch from'),1)
        self.assertEqual(result.count("<OfficialKnowledgeSearch project="),1)

    def test_unknown_component_fails_before_writing(self):
        original=b'const KnowledgePage=()=>null;'
        with self.assertRaisesRegex(RuntimeError,"KnowledgeStart"):
            installer.adapt_parent(original)
        self.assertEqual(original,b'const KnowledgePage=()=>null;')

    def test_original_target_local_project_still_works(self):
        original=(SCRIPTS.parent/"web/bi_factory/src/KnowledgeStart.jsx").read_bytes()
        result=installer.adapt_parent(original)
        self.assertEqual(installer.adapt_parent(result),result)

if __name__=="__main__":
    unittest.main(verbosity=2)
