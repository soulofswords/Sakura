const fs=require('fs'),path=require('path');
const obfuscator=require('./hardening-node/node_modules/javascript-obfuscator');
const [input,output]=process.argv.slice(2);if(!input||!output)throw Error('Pass input and output folders');
fs.mkdirSync(output,{recursive:true});
for(const entry of fs.readdirSync(input,{withFileTypes:true})){
 if(!entry.isFile()||!entry.name.endsWith('.js'))continue;
 const source=fs.readFileSync(path.join(input,entry.name),'utf8');
 const result=obfuscator.obfuscate(source,{compact:true,identifierNamesGenerator:'hexadecimal',renameGlobals:false,
  renameProperties:false,stringArray:true,stringArrayEncoding:['base64'],stringArrayThreshold:.6,
  controlFlowFlattening:false,deadCodeInjection:false,selfDefending:false,debugProtection:false,
  disableConsoleOutput:false,sourceMap:false,seed:20261013,target:'browser'});
 fs.writeFileSync(path.join(output,entry.name),result.getObfuscatedCode());
}
console.log('Obfuscated application JavaScript:',output);
