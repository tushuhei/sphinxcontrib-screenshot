.. screencast:: ./resources/anim.html
   :viewport-width: 320
   :viewport-height: 200
   :trim-start: 0.3
   :interactions:
     document.getElementById('b').click();
     await new Promise(r => setTimeout(r, 800));
