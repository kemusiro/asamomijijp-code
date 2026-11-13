// SPDX-License-Identifier: MIT
// Modelled Web Serial only;never opens an actual device.
import { chromium } from '@playwright/test';
import { fileURLToPath } from 'node:url';
import { readFile } from 'node:fs/promises';
const browser=await chromium.launch({headless:true});
try{
 const page=await browser.newPage();
 await page.addInitScript(()=>{
  window.sent=[];let controller;
  const port={open:async()=>{},setSignals:async()=>{},close:async()=>{},
   readable:new ReadableStream({start(c){controller=c;}}),
   writable:new WritableStream({write(bytes){const command=new TextDecoder().decode(bytes);window.sent.push(command);if(command==='help\n'||command.startsWith('fm ')||command.startsWith('bus ')){const legacy=location.search.includes('legacy');const gain=command.startsWith('fm ')?command.trim().slice(3):'8';controller.enqueue(new TextEncoder().encode('STATUS C='+(location.search.includes('newmidi')?'0.5.0-alpha.1':location.search.includes('newstream')?'0.4.0-alpha.2':'0.3.0-alpha.'+(legacy?'1':location.search.includes('alpha2')?'2':location.search.includes('alpha3')?'3':location.search.includes('alpha4')?'4':location.search.includes('alpha5')?'5':location.search.includes('alpha6')?'6':'7'))+' audio_ready=1 fault=0 state=0 events=0/0 gates=0'+(legacy?'':' fm_gain_eighths='+gain)+'\r\n'));}}})};
  Object.defineProperty(navigator,'serial',{value:{requestPort:async()=>port}});
  window.reply=text=>controller.enqueue(new TextEncoder().encode(text));
  window.dumpReply=(bad=false)=>{
    const bytes=new Uint8Array(432150);bytes.set([82,67,68,49]);
    for(let i=96;i<bytes.length;i++)bytes[i]=(i*17)&255;
    let crc=0xffffffff;for(const byte of bytes){crc^=byte;for(let b=0;b<8;b++)crc=(crc>>>1)^((crc&1)?0xedb88320:0);}
    crc=((crc^0xffffffff)>>>0)^(bad?1:0);let text='DIAGBEGIN 432150 '+(crc>>>0).toString(16).padStart(8,'0')+'\r\n';
    for(let i=0;i<bytes.length;i+=128)text+='DIAGDATA '+Array.from(bytes.slice(i,i+128),b=>b.toString(16).padStart(2,'0')).join('')+'\r\n';
    text+='DIAGEND\r\n';
    // Deliberately break the serial payload at non-line boundaries.
    for(let i=0;i<text.length;i+=997)controller.enqueue(new TextEncoder().encode(text.slice(i,i+997)));
  };
 });
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url)));
 if(!await page.locator('#play').isDisabled()||!await page.locator('#capture').isDisabled())throw new Error('Sound enabled before identification');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('play').disabled);
 if(JSON.stringify(await page.evaluate(()=>window.sent))!==JSON.stringify(['help\n']))throw new Error('Unsolicited sound command');
 await page.locator('#fm').selectOption('12');await page.waitForFunction(()=>window.sent.includes('fm 12\n'));
 await page.locator('#bus').selectOption('slow');await page.waitForFunction(()=>window.sent.includes('bus slow\n'));
 await page.locator('#test').click();await page.locator('#play').click();await page.locator('#stop').click();
 const sent=await page.evaluate(()=>window.sent);
 if(JSON.stringify(sent)!==JSON.stringify(['help\n','fm 12\n','bus slow\n','test\n','play\n','stop\n']))throw new Error('Control command mismatch');
 // Capture is explicit;fixed FM during acquisition;dump only after completion.
 await page.locator('#capture').click();await page.waitForFunction(()=>window.sent.includes('capture 31\n'));
 if(!await page.locator('#fm').isDisabled()||!await page.locator('#dump').isDisabled())throw new Error('Capture controls unsafe');
 await page.evaluate(()=>window.reply('STOP diagnostic capture complete\r\nDONE diagnostic snapshot ready\r\nDIAG state=3 ready=1 bytes=432150\r\n'));
 await page.waitForFunction(()=>!document.getElementById('dump').disabled);
 let downloads=0;page.on('download',()=>downloads++);
 // A device cannot cause an unsolicited download without a user dump request.
 await page.evaluate(()=>window.dumpReply());await page.waitForTimeout(100);
 if(downloads)throw new Error('Unsolicited diagnostic download');
 const downloaded=page.waitForEvent('download');await page.locator('#dump').click();await page.evaluate(()=>window.dumpReply());
 const file=await downloaded;const bytes=await readFile(await file.path());
 if(bytes.length!==432150||bytes.subarray(0,4).toString()!=='RCD1'||bytes[12345]!==((12345*17)&255))throw new Error('Diagnostic content corrupted');
 await page.waitForFunction(()=>!document.getElementById('dump').disabled);
 await page.locator('#dump').click();await page.evaluate(()=>window.dumpReply(true));
 await page.waitForFunction(()=>document.getElementById('state').textContent.includes('検査に失敗'));
 if(downloads!==1)throw new Error('Corrupted diagnostic was downloaded');
 await page.locator('#dump').click();await page.evaluate(()=>window.reply('DIAGBEGIN 999999999 ffffffff\r\n'));
 await page.waitForFunction(()=>document.getElementById('state').textContent.includes('サイズが不正'));
 await page.evaluate(()=>window.reply('FAIL fault=2\r\n'));await page.waitForFunction(()=>document.getElementById('play').disabled);
 await page.locator('#disconnect').click();await page.waitForFunction(()=>!document.getElementById('connect').disabled);
 if(!await page.locator('#play').isDisabled())throw new Error('Play enabled after close');
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?legacy');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('bootsel').disabled);
 if(await page.locator('#fm').inputValue()!=='1')throw new Error('Legacy gain display incorrect');
 if(!await page.locator('#fm').isDisabled())throw new Error('Gain enabled for alpha1 firmware');
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?alpha2');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('fm').disabled);
 if(!await page.locator('#bus').isDisabled())throw new Error('Bus timing enabled for alpha2 firmware');
 if(!await page.locator('#fm option[value="12"]').isDisabled())throw new Error('Boost enabled for alpha2 firmware');
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?alpha3');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('fm').disabled);
 if(!await page.locator('#capture').isDisabled())throw new Error('Capture enabled for alpha3 firmware');
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?alpha4');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('capture').disabled);
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?alpha5');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('capture').disabled);
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?alpha6');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('capture').disabled);
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?newstream');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('play').disabled);
 await page.evaluate(()=>window.reply('I2C protocol=2 address=0x42 state=1 result=0 error=0\r\n'));
 await page.waitForFunction(()=>document.getElementById('play').disabled);
 if(!await page.locator('#capture').isDisabled()||!await page.locator('#bus').isDisabled()||await page.locator('#stop').isDisabled())throw new Error('I2C ownership gating incorrect');
 await page.evaluate(()=>window.reply('I2C protocol=2 address=0x42 state=3 result=0 error=0\r\n'));
 await page.waitForFunction(()=>!document.getElementById('play').disabled);
 await page.goto('file://'+fileURLToPath(new URL('pc/revc-console.html',import.meta.url))+'?newmidi');
 await page.locator('#connect').click();await page.waitForFunction(()=>!document.getElementById('play').disabled);
 await page.evaluate(()=>window.reply('MIDI protocol=1 owned=1 state=3 mask=63 gate=1\r\n'));
 await page.waitForFunction(()=>document.getElementById('play').disabled);
 if(!await page.locator('#test').isDisabled()||!await page.locator('#capture').isDisabled()||!await page.locator('#bus').isDisabled()||await page.locator('#stop').isDisabled())throw new Error('MIDI ownership gating incorrect');
 await page.evaluate(()=>window.reply('MIDI protocol=1 owned=0 state=0 mask=0 gate=0\r\n'));
 await page.waitForFunction(()=>!document.getElementById('play').disabled);
 console.log('PASS: no auto-play,firmware identification,test/play/stop commands,gain boost,bus timing selection,alpha1..7 and0.4 I2C ownership compatibility,explicit bounded CRC-checked diagnostic download and rejection of unsolicited/corrupt/oversized data,fault gating and disconnect;Web Serial is modelled');
}finally{await browser.close();}
