// Interactive tools for the ITEC 4235 notes: Caesar breaker, RSA calculator, permission decoder.
// The site shell calls this after the notes are rendered.
function initTools() {

  // Caesar tool
  function shift(t,k){
    k=((k%26)+26)%26;
    return t.replace(/[a-z]/gi,function(c){
      var b=c<='Z'?65:97; return String.fromCharCode((c.charCodeAt(0)-b+k)%26+b);
    });
  }
  var czIn=document.getElementById('cz-in'), czK=document.getElementById('cz-k'), czOut=document.getElementById('cz-out');
  function kval(){var k=parseInt(czK.value,10); return isNaN(k)?0:k;}
  document.getElementById('cz-enc').addEventListener('click',function(){czOut.textContent=shift(czIn.value,kval());});
  document.getElementById('cz-dec').addEventListener('click',function(){czOut.textContent=shift(czIn.value,-kval());});
  document.getElementById('cz-all').addEventListener('click',function(){
    var lines=[]; for(var k=0;k<26;k++){lines.push('decrypt k='+(k<10?' ':'')+k+': '+shift(czIn.value,-k));}
    czOut.textContent=lines.join('\n');
  });

  // RSA tool (BigInt)
  function big(s){s=String(s).trim(); if(!/^\d+$/.test(s)) throw new Error('Use whole numbers only.'); return BigInt(s);}
  function mod(a,n){var r=a%n; return r<0n?r+n:r;}
  function gcd(a,b){while(b>0n){var t=a%b;a=b;b=t;}return a;}
  function isPrime(n){if(n<2n)return false; if(n<4n)return true; if(n%2n===0n)return false; for(var i=3n;i*i<=n;i+=2n){if(n%i===0n)return false;} return true;}
  function powmod(b,e,n){var r=1n;b=mod(b,n);while(e>0n){if(e&1n)r=r*b%n;b=b*b%n;e>>=1n;}return r;}
  function inverseTable(e,phi){
    var rows=[[phi,phi,'—'],[e,1n,'—']], L0=phi,R0=phi,L1=e,R1=1n, guard=0;
    while(L1!==1n && L1!==0n && guard++<200){
      var q=L0/L1, L2=L0-q*L1, R2=mod(R0-q*R1,phi);
      rows.push([L2,R2,String(q)]);
      L0=L1;R0=R1;L1=L2;R1=R2;
    }
    return {rows:rows, d:(L1===1n?R1:null)};
  }
  document.getElementById('r-go').addEventListener('click',function(){
    var out=document.getElementById('r-out');
    try{
      var p=big(document.getElementById('r-p').value), q=big(document.getElementById('r-q').value),
          e=big(document.getElementById('r-e').value), M=big(document.getElementById('r-m').value);
      if(p>1000000n||q>1000000n) throw new Error('Keep p and q under 1,000,000 for this study tool.');
      var lines=[];
      if(!isPrime(p)) lines.push('Warning: p = '+p+' is not prime.');
      if(!isPrime(q)) lines.push('Warning: q = '+q+' is not prime.');
      if(p===q) lines.push('Warning: p and q should be different primes.');
      var n=p*q, phi=(p-1n)*(q-1n);
      lines.push('n = p·q = '+p+' × '+q+' = '+n);
      lines.push('φ(n) = (p−1)(q−1) = '+(p-1n)+' × '+(q-1n)+' = '+phi);
      var g=gcd(e,phi);
      lines.push('gcd(e, φ) = gcd('+e+', '+phi+') = '+g);
      if(g!==1n||e<=1n||e>=phi){ lines.push('e must satisfy 1 < e < φ and gcd(e, φ) = 1. Pick a different e.'); out.textContent=lines.join('\n'); return; }
      var t=inverseTable(e,phi);
      lines.push('');
      lines.push('Finding d (two-column method, left ≡ right × e mod φ):');
      lines.push('  left'.padEnd(14)+'right'.padEnd(14)+'q');
      t.rows.forEach(function(r){lines.push('  '+String(r[0]).padEnd(12)+String(r[1]).padEnd(14)+r[2]);});
      var d=t.d;
      lines.push('d = '+d+'   check: '+e+' × '+d+' mod '+phi+' = '+mod(e*d,phi));
      lines.push('');
      lines.push('Public key (e, n) = ('+e+', '+n+')    Private key d = '+d);
      if(M>=n){ lines.push('M must be smaller than n = '+n+'.'); out.textContent=lines.join('\n'); return; }
      var C=powmod(M,e,n), M2=powmod(C,d,n);
      lines.push('Encrypt: C = '+M+'^'+e+' mod '+n+' = '+C);
      lines.push('Decrypt: M = '+C+'^'+d+' mod '+n+' = '+M2+(M2===M?'  ✓':'  ✗'));
      out.textContent=lines.join('\n');
    }catch(err){ out.textContent=err.message; }
  });

  // Permission decoder
  document.getElementById('pm-go').addEventListener('click',function(){
    var v=document.getElementById('pm-in').value.trim(), out=document.getElementById('pm-out');
    var who=['User (owner)','Group','Other'], str='', oct='';
    function tri(d){return (d&4?'r':'-')+(d&2?'w':'-')+(d&1?'x':'-');}
    if(/^[0-7]{3,4}$/.test(v)){
      var digs=v.slice(-3).split('').map(Number); oct=v; str=digs.map(tri).join('');
      if(v.length===4){var sp=Number(v[0]); if(sp&4) str=str.slice(0,2)+(str[2]==='x'?'s':'S')+str.slice(3); if(sp&2) str=str.slice(0,5)+(str[5]==='x'?'s':'S')+str.slice(6);}
    } else {
      var s=v.replace(/^[-dlcbps](?=.{9}$)/,'');
      if(!/^[r-][w-][xsS-][r-][w-][xsS-][r-][w-][xtT-]$/.test(s)){ out.textContent='Enter 9 characters like rwxr-xr-- (an optional leading type letter is fine) or octal like 754 / 4755.'; return; }
      str=s; var special=0, digits='';
      for(var i=0;i<3;i++){
        var t3=s.substr(i*3,3), d=0;
        if(t3[0]==='r')d+=4; if(t3[1]==='w')d+=2; if(/[xst]/.test(t3[2]))d+=1;
        if(i===0&&/[sS]/.test(t3[2]))special+=4; if(i===1&&/[sS]/.test(t3[2]))special+=2; if(i===2&&/[tT]/.test(t3[2]))special+=1;
        digits+=d;
      }
      oct=(special?String(special):'')+digits;
    }
    var lines=['String: '+str,'Octal:  '+oct,''];
    for(var j=0;j<3;j++){
      var part=str.substr(j*3,3), can=[];
      if(part[0]==='r')can.push('read'); if(part[1]==='w')can.push('write'); if(/[xst]/.test(part[2]))can.push('execute');
      lines.push(who[j].padEnd(14)+part+'  → '+(can.length?can.join(', '):'no access'));
    }
    if(/[sS]/.test(str[2])) lines.push('\nsetuid bit set: runs with the file owner\'s privileges.');
    if(/[sS]/.test(str[5])) lines.push('setgid bit set: runs with the file group\'s privileges.');
    out.textContent=lines.join('\n');
  });
}
