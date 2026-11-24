"""A instalação adiciona a pesquisa à tela local sem reescrevê-la."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
module_path=HERE/"instalar_conhecimento_oficial_compat.py"
spec=importlib.util.spec_from_file_location("knowledge_compat_installer",module_path)
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class KnowledgeLocalCompatibilityTests(unittest.TestCase):
    def test_insert_into_existing_component_and_keep_original_fields(self):
        original=(
            'import React from "react";\n'
            'export default function KnowledgeStart({project,onProjectChanged}){\n'
            ' const registrar=()=>true;\n'
            ' return <div className="card" style={{display:"grid",gap:16}}>\n'
            ' <h2>Cadastro local personalizado</h2>\n'
            ' <input aria-label="Tema já existente" />\n'
            ' <button onClick={registrar}>Meu botão</button>\n'
            ' </div>;\n'
            '}\n'
        ).encode()
        out=installer.inject_knowledge_ui(original)
        text=out.decode()
        self.assertIn('import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";',text)
        self.assertIn("<OfficialKnowledgeSearch project={project}/>",text)
        self.assertIn("<h2>Cadastro local personalizado</h2>",text)
        self.assertIn('aria-label="Tema já existente"',text)
        self.assertIn("const registrar=()=>true;",text)
        self.assertIn('<button onClick={registrar}>Meu botão</button>',text)
        self.assertEqual(out.count(b"BI_KNOWLEDGE_OFFICIAL_SLOT"),1)
        self.assertEqual(out,installer.inject_knowledge_ui(out))
        import_line=b'import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch.jsx";\\n'.replace(b"\\\\n",b"\\n")
        injected=b'\\n  {/* BI_KNOWLEDGE_OFFICIAL_SLOT: pesquisa oficial adicionada sem substituir o cadastro */}\\n  <OfficialKnowledgeSearch project={project}/>\\n'.replace(b"\\\\n",b"\\n")
        self.assertEqual(out.replace(import_line,b"",1).replace(injected,b"",1),original,
                         "A inserção deve poder ser revertida exatamente, byte a byte")

    def test_prepend_local_comments_and_multiline_return(self):
        original=(
            "// customizações feitas no Codespaces\n"
            "import React from 'react';\n"
            "export default function KnowledgeStart({project}) {\n"
            " const alpha = 42;\n"
            " return (\n"
            "  <main className='knowledge'>\n"
            "    <p>Meu componente personalizado</p>\n"
            "  </main>\n"
            " );\n"
            "}\n"
        ).encode()
        data=installer.inject_knowledge_ui(original)
        text=data.decode()
        self.assertIn("const alpha = 42",text)
        self.assertIn("// customizações feitas no Codespaces",text)
        self.assertTrue(text.startswith("// customizações feitas no Codespaces\\n".replace("\\\\n","\\n")), "Cabeçalho local deve continuar na primeira linha")
        self.assertIn("<main className='knowledge'>",text)
        self.assertIn("<OfficialKnowledgeSearch project={project}/>",text)

    def test_old_page_with_its_own_search_is_not_duplicated(self):
        source=(
            'export default function KnowledgeStart({project}){\n'
            ' const r=request(base+"/discover");\n'
            ' const s=request(base+"/approve");\n'
            ' return <div>Pesquisa já integrada</div>;\n'
            '}\n'
        ).encode()
        self.assertEqual(source,installer.inject_knowledge_ui(source))

    def test_unsupported_component_fails_without_modification(self):
        source=b"const CustomPage=()=>null;\n"
        with self.assertRaisesRegex(RuntimeError,"KnowledgeStart"):
            installer.inject_knowledge_ui(source)
        self.assertEqual(source,b"const CustomPage=()=>null;\n")

    def test_target_contains_standalone_search_component(self):
        path=HERE.parent/"web/bi_factory/src/OfficialKnowledgeSearch.jsx"
        component=path.read_text(encoding="utf-8")
        self.assertIn('export default function OfficialKnowledgeSearch({project})',component)
        self.assertIn('"/discover"',component)
        self.assertIn('"/approve"',component)
        self.assertIn('"research_result"',component)
        self.assertNotIn("window.location=",component)

if __name__=="__main__":
    unittest.main(verbosity=2)
