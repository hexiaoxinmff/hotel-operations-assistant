import fs from 'node:fs/promises';
import path from 'node:path';
import {constants} from 'node:fs';
import {randomUUID} from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const [configPath,inputPath,outputPath]=process.argv.slice(2);
if(!configPath||!inputPath||!outputPath)throw Error('Usage: table_output.mjs config.json input.json output.xlsx');
const c=JSON.parse(await fs.readFile(configPath,'utf8'));
const [state,req,plan]=process.argv.slice(5);
if(!state||!req||!plan)throw Error('Workflow path, requirement version and plan version required after output path');
execFileSync(c.python,['-B',path.join(path.dirname(fileURLToPath(import.meta.url)),'workflow_guard.py'),'--state',state,'check','--action','office','--requirement-version',req,'--plan-version',plan],{stdio:'pipe'});
async function confined(target,roots,write=false){
 const full=path.resolve(target);
 for(let p=full;;p=path.dirname(p)){
  try{if((await fs.lstat(p)).isSymbolicLink())throw Error('Symlink/reparse path rejected');}catch(e){if(e.code!=='ENOENT')throw e;}
  if(path.dirname(p)===p)break;
 }
 const ok=roots.some(root=>{const r=path.relative(path.resolve(root),full);return r===''||(!r.startsWith('..'+path.sep)&&r!=='..'&&!path.isAbsolute(r));});
 if(!ok)throw Error('Outside configured roots');
 if(write){try{await fs.access(full);throw Error('Output exists');}catch(e){if(e.code!=='ENOENT')throw e;}}
 return full;
}
const source=await confined(inputPath,c.read_roots);const target=await confined(outputPath,c.write_roots,true);
const data=JSON.parse(await fs.readFile(source,'utf8'));const rows=data.rows;
if(!Array.isArray(rows)||!rows.length||!rows[0].length||rows[0].length>20||rows.length>10000||!rows.every(r=>Array.isArray(r)&&r.length===rows[0].length))throw Error('Expected rectangular rows, <=20 columns / 10000 rows');
if(!rows.every(r=>r.every(v=>v===null||['string','number','boolean'].includes(typeof v))))throw Error('Unsupported cell value');
const require=createRequire(path.join(c.artifact_modules,'_hotel_resolve.cjs'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(require.resolve('@oai/artifact-tool')).href);
const wb=Workbook.create();const sh=wb.worksheets.add('结果');
const col=n=>{let r='';while(n){const x=(n-1)%26;r=String.fromCharCode(65+x)+r;n=Math.floor((n-1)/26);}return r;};
const last=col(rows[0].length);sh.getRange(`A1:${last}${rows.length}`).values=rows.map(r=>r.map(v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v));
sh.getRange(`A1:${last}${rows.length}`).format.columnWidth=22;sh.getRange(`A1:${last}${rows.length}`).format.rowHeight=26;sh.getRange(`A1:${last}${rows.length}`).format.wrapText=true;
sh.getRange(`A1:${last}1`).format.fill='#E7EEF5';sh.getRange(`A1:${last}1`).format.font.bold=true;
wb.recalculate();await fs.mkdir(path.dirname(target),{recursive:true});
const file=await SpreadsheetFile.exportXlsx(wb);const temp=target+'.'+randomUUID()+'.tmp.xlsx';
try{await file.save(temp);await fs.copyFile(temp,target,constants.COPYFILE_EXCL);}finally{await fs.unlink(temp).catch(()=>{});}
console.log(JSON.stringify({output:target,status:'GENERATED_REQUIRES_REVIEW',preview:'Use platform spreadsheet renderer; export does not prove visual layout'}));
