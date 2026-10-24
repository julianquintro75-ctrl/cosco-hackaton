(function(){
  function safe(fn,n){try{fn()}catch(e){console.warn('init '+n,e)}}
  function reveal(){
    var els=[].slice.call(document.querySelectorAll('.reveal'));
    if(!('IntersectionObserver' in window)){els.forEach(function(e){e.classList.add('in')});return}
    var io=new IntersectionObserver(function(es){es.forEach(function(x){if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}})},{threshold:0.05});
    els.forEach(function(e){io.observe(e)});
    setTimeout(function(){els.forEach(function(e){e.classList.add('in')})},6000);
  }
  document.documentElement.classList.add('js');
  safe(reveal,'reveal');
})();
