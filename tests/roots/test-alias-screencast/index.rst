.. screencast:: ./anim.html
   :alias: my-cast
   :poster:
   :viewport-width: 320
   :viewport-height: 200
   :interactions:
     document.getElementById('b').click();
     await new Promise(r => setTimeout(r, 300));
