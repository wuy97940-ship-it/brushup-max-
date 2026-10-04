// 离线包仅缓存程序资源；学习存档不进入网络或Service Worker缓存。
(function () {
  function status(value) {
    window.xiaoyuanOffline = value;
    window.dispatchEvent(new CustomEvent('xiaoyuan-offline', {detail: value}));
  }
  if (!('serviceWorker' in navigator) || !window.isSecureContext) {
    status('unsupported');
    return;
  }
  var registration;
  var requestedUpdate = false;
  status('preparing');
  window.xiaoyuanApplyUpdate = function () {
    if (registration && registration.waiting) {
      requestedUpdate = true;
      registration.waiting.postMessage({type: 'SKIP_WAITING'});
    }
  };
  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (requestedUpdate) window.location.reload();
  });
  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', {updateViaCache: 'none'}).then(function (r) {
      registration = r;
      if (r.waiting) status('update');
      function watch(worker) {
        if (!worker) return;
        function changed() {
          if (worker.state === 'installed' && r.active) status('update');
          if (worker.state === 'redundant' && !r.active) status('error');
        }
        worker.addEventListener('statechange', changed);
        changed();
      }
      watch(r.installing);
      r.addEventListener('updatefound', function () {watch(r.installing);});
      return navigator.serviceWorker.ready;
    }).then(function () {
      status(registration.waiting ? 'update' : 'ready');
    }).catch(function () {status('error');});
  });
})();
