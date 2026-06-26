(function () {
  function debounceReload() {
    if (window.__roundLiveReloading) return;
    window.__roundLiveReloading = true;
    setTimeout(function () {
      window.location.reload();
    }, 120);
  }

  window.startRoundLiveReload = function startRoundLiveReload(options) {
    options = options || {};
    var eventId = options.eventId;
    var roundNo = options.roundNo;
    var knownVersion = options.version || null;

    if (!eventId) return;

    var hasRound = !(roundNo === null || roundNo === undefined || roundNo === '' || roundNo === 'null');

    function isSameScope(data) {
      if (!data || String(data.event_id) !== String(eventId)) return false;
      if (!hasRound) return true;
      return String(data.round_no) === String(roundNo);
    }

    // ไม่ใช้ polling แล้ว เพื่อไม่ให้หน้าใบประกบ/ใบบันทึกยิง request ซ้ำ ๆ
    // หน้าเหล่านี้จะรอเฉย ๆ และ reload เฉพาะตอนหน้า swith กดสลับแล้ว server ส่งสัญญาณมาเท่านั้น
    if (typeof io !== 'function') return;

    try {
      var socket = window.roundLiveSocket || window.socket || io();
      window.roundLiveSocket = socket;

      function joinRoom() {
        socket.emit('join_round', { event_id: eventId, round_no: hasRound ? roundNo : null });
      }

      if (socket.connected) joinRoom();
      socket.on('connect', joinRoom);

      socket.on('round_pairing_updated', function (data) {
        if (!isSameScope(data)) return;
        if (!knownVersion || data.version !== knownVersion) {
          debounceReload();
        }
      });

      socket.on('event_pairing_updated', function (data) {
        if (hasRound) return;
        if (!isSameScope(data)) return;
        debounceReload();
      });
    } catch (err) {
      // เงียบไว้ ไม่รบกวนหน้าพิมพ์/ใบบันทึก
    }
  };
})();
