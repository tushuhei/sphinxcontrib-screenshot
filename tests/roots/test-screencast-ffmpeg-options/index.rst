.. screencast:: ./resources/anim.html
   :viewport-width: 320
   :viewport-height: 200
   :controls:
   :ffmpeg-options: -an -c:v libvpx -b:v 0 -crf 40 -qmin 0 -qmax 50 -deadline good
   :interactions:
     document.getElementById('b').click();
