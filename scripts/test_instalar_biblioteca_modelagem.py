"""Regressão do instalador: preservar DataWorkspace local e integrar contexto uma única vez."""
from __future__ import annotations
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
PATH=HERE/"instalar_biblioteca_ia_modelagem.py"
spec=importlib.util.spec_from_file_location("bi_knowledge_installer",PATH)
deploy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)

class ModelInstallerTests(unittest.TestCase):
 def test_user_customization_is_preserved_and_injection_is_idempotent(self):
    original=(
      "// comentário do usuário, não remover\n"
      "import React from 'react';\n"
      "export default function DataWorkspace({area,projectId}){\n"
      " const fields=[{original_name:'empenho'}];\n"
      " const mensagem='Meu cadastro não pode ser apagado';\n"
      " return <div className='custom'>\n"
      " {area===\"Modelagem\"&&<>\n"
      "  <h3>Pipeline de modelagem recuperado</h3>\n"
      "  <p>{mensagem}</p>\n"
      " </>}\n"
      " </div>;\n"
      "}\n"
    ).encode()
    updated=deploy.insert_model_component(original)
    text=updated.decode()
    self.assertTrue(text.startswith("// comentário do usuário, não remover\n"))
    self.assertIn("Meu cadastro não pode ser apagado",text)
    self.assertIn('<ModelKnowledgeContext projectId={projectId} fields={fields}/>',text)
    self.assertIn("const fields=",text)
    self.assertEqual(updated,deploy.insert_model_component(updated))
    # Remove only what the installer inserted; all user code should be identical.
    header=b'import ModelKnowledgeContext from "./ModelKnowledgeContext.jsx";\n'
    slot=b'\n        {/* BI_KNOWLEDGE_MODEL_CONTEXT */}\n        <ModelKnowledgeContext projectId={projectId} fields={fields}/>'
    self.assertEqual(updated.replace(header,b"",1).replace(slot,b"",1),original)

 def test_missing_modeling_anchor_fails_safely(self):
    original=b"const fields=[]; const projectId='p1'; function Other(){return null;}"
    with self.assertRaisesRegex(RuntimeError,"Modelagem"):
        deploy.insert_model_component(original)

 def test_subprocess_sees_isolated_pypdf_target(self):
    # Reproduz a falha real do Codespaces: pip --target não altera sys.path.
    import os
    import sys
    from unittest.mock import patch
    with patch.object(deploy.subprocess,"run") as executed:
        deploy.run([sys.executable,"-c","import pypdf"])
    kwargs=executed.call_args.kwargs
    self.assertTrue(kwargs["check"])
    self.assertEqual(kwargs["cwd"],deploy.ROOT)
    self.assertEqual(kwargs["env"]["PYTHONPATH"].split(os.pathsep)[0],
                     str(deploy.ROOT/".git"/"knowledge-deps"))
    self.assertEqual(executed.call_args.args[0][1:],["-c","import pypdf"])

 def test_repository_current_file_is_already_integrated(self):
    path=HERE.parent/"web/bi_factory/src/DataWorkspace.jsx"
    raw=path.read_bytes()
    self.assertEqual(deploy.insert_model_component(raw),raw)
    self.assertIn("ModelKnowledgeContext",raw.decode())

if __name__=="__main__":
 unittest.main(verbosity=2)
