#!/usr/bin/env python3
"""Targeted static scan for subtitle-font and demo-resolver augmentation hooks."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/"_vendor"))
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM  # noqa:E402

TARGETS={
 "static_renderer_81_82":"0x0015E60C",
 "static_renderer_83":"0x0015EC64",
 "demo_command_handler":"0x00409DB0",
 "demo_descriptor_loader":"0x004449CC",
 "demo_request_consumer":"0x004BC2DC",
 "tagged_argument_decoder":"0x00171C7C",
 "movie_handler":"0x0079F6B4",
}

def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("image",type=Path);p.add_argument("manifest",type=Path);p.add_argument("output",type=Path);p.add_argument("--radius",type=lambda x:int(x,0),default=0x100);a=p.parse_args()
 image=a.image.read_bytes(); manifest=json.loads(a.manifest.read_text()); text=manifest["segments"]["text"]; base=text["va"]; start=text["file_start"]; size=text["size"]
 md=Cs(CS_ARCH_ARM,CS_MODE_ARM); result={"format":"mgs3d-augmentation-structure-scan-v1","image":str(a.image),"targets":{}}
 for name,raw in TARGETS.items():
  va=int(raw,16); off=start+(va-base); lo=max(start,off-a.radius); hi=min(start+size,off+a.radius)
  ins=[]
  for i in md.disasm(image[lo:hi],base+(lo-start)):
   ins.append({"address":f"0x{i.address:08X}","mnemonic":i.mnemonic,"operands":i.op_str,"target":i.address==va})
  # Direct ARM BL encodes a signed imm24 relative to PC+8. Capstone exposes
  # the resolved target in operand text, making a bounded caller inventory.
  callers=[]
  for i in md.disasm(image[start:start+size],base):
   if i.mnemonic in {"bl","blx"} and i.op_str.lower()==f"#0x{va:x}": callers.append(f"0x{i.address:08X}")
  result["targets"][name]={"va":raw,"file_offset":off,"direct_callers":callers,"window":ins}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+"\n");
 for n,v in result["targets"].items():
  print(n,v["va"],"callers",len(v["direct_callers"]))
 return 0
if __name__=="__main__":raise SystemExit(main())
