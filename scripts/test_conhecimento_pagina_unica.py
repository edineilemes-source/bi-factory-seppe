"""Confere a rota única Conhecimento e preservação do código local antigo."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/"scripts"
spec=importlib.util.spec_from_file_location(
    "install_single_knowledge", SCRIPTS/"instalar_pesquisa_multifontes.py")
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class SingleKnowledgeRouteTests(unittest.TestCase):
    def test_local_main_changes_only_import_and_mount(self):
        source=(
            'import React from "react";\n'
            'import KnowledgeStart from "./KnowledgeStart";\n'
            'import DataWorkspace from "./DataWorkspace";\n'
            'function App(){\n'
            ' const activeProject={id:"abc"};\n'
            ' return <main><DataWorkspace area="Modelagem"/>'
            '{section==="Conhecimento"&&activeProject?'
            '<KnowledgeStart key={activeProject.id} project={activeProject} '
            'onProjectChanged={updateBusinessProject}/>:null}</main>;\n'
            '}\n'
        ).encode()
        target=installer.adapt_main(source)
        expected=source.decode().replace(
            'import KnowledgeStart from "./KnowledgeStart";',
            'import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch";').replace(
            '<KnowledgeStart','<OfficialKnowledgeSearch').encode()
        self.assertEqual(target,expected)
        self.assertEqual(installer.adapt_main(target),target)
        self.assertIn(b'<DataWorkspace area="Modelagem"/>',target)
        self.assertNotIn(b'<KnowledgeStart',target)

    def test_main_with_single_quotes_and_extensions(self):
        source=(
            "import KnowledgeStart from './KnowledgeStart.jsx';\n"
            'const App=()=>section==="Conhecimento"?'
            '<KnowledgeStart project={selected}/>:null;\n'
        ).encode()
        out=installer.adapt_main(source).decode()
        self.assertEqual(out.count('<OfficialKnowledgeSearch'),1)
        self.assertIn('import OfficialKnowledgeSearch',out)

    def test_unknown_or_duplicated_routes_are_refused(self):
        for content in (
            'import React from "react";\nfunction App(){return <div/>}',
            'import KnowledgeStart from "./KnowledgeStart";'
            'const x=<><KnowledgeStart/><KnowledgeStart/></>;',
            'import KnowledgeStart from "./KnowledgeStart";'
            'const x=<><KnowledgeStart/><OfficialKnowledgeSearch/></>;',
        ):
            raw=content.encode()
            with self.assertRaisesRegex(RuntimeError,"Conhecimento|Import"):
                installer.adapt_main(raw)
            self.assertEqual(raw,content.encode())

    def test_versioned_main_uses_single_official_page(self):
        source=(ROOT/"web/bi_factory/src/main.jsx").read_text(encoding="utf8")
        self.assertIn('import OfficialKnowledgeSearch from "./OfficialKnowledgeSearch";',source)
        self.assertEqual(source.count("<OfficialKnowledgeSearch"),1)
        self.assertNotIn("<KnowledgeStart",source)
        self.assertEqual(installer.adapt_main(source.encode()),source.encode())

    def test_legacy_page_retained_but_not_mounted(self):
        legacy=(ROOT/"web/bi_factory/src/KnowledgeStart.jsx").read_text(encoding="utf8")
        main=(ROOT/"web/bi_factory/src/main.jsx").read_text(encoding="utf8")
        self.assertIn("ETAPA 1 · CONHECIMENTO DO NEGÓCIO",legacy)
        self.assertNotIn("KnowledgeStart",main)
        official=(ROOT/"web/bi_factory/src/OfficialKnowledgeSearch.jsx").read_text(encoding="utf8")
        self.assertIn('latestUniqueResearch',official)
        self.assertIn("Adicionar documento próprio (opcional)",official)
        self.assertEqual(official.count("<KnowledgeLibrary"),1)

if __name__=="__main__":
    unittest.main(verbosity=2)
