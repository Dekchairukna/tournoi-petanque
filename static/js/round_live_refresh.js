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

    var fallbackTimer = null;
    var liveVersionUrl = hasRound
      ? '/event/' + encodeURIComponent(eventId) + '/round/' + encodeURIComponent(roundNo) + '/live-version'
      : '/event/' + encodeURIComponent(eventId) + '/live-version';

    function stopFallbackPolling() {
      if (!fallbackTimer) return;
      clearInterval(fallbackTimer);
      fallbackTimer = null;
    }

    async function pollLiveVersion() {
      try {
        var response = await fetch(liveVersionUrl, { cache: 'no-store' });
        if (!response.ok) return;
        var data = await response.json();
        if (!data || !data.ok) return;
        if (knownVersion && data.version && data.version !== knownVersion) {
          debounceReload();
          return;
        }
        if (!knownVersion && data.version) knownVersion = data.version;
      } catch (err) {
        // เครือข่ายยังไม่กลับมา ให้รอบถัดไปลองใหม่เอง
      }
    }

    function startFallbackPolling() {
      if (fallbackTimer) return;
      pollLiveVersion();
      fallbackTimer = setInterval(pollLiveVersion, 5000);
    }

    if (typeof io !== 'function') {
      startFallbackPolling();
      return;
    }

    try {
      var socket = window.roundLiveSocket || window.socket || io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        timeout: 10000
      });
      window.roundLiveSocket = socket;

      function joinRoom() {
        stopFallbackPolling();
        socket.emit('join_round', { event_id: eventId, round_no: hasRound ? roundNo : null });
      }

      if (socket.connected) joinRoom();
      socket.on('connect', joinRoom);
      socket.on('disconnect', startFallbackPolling);
      socket.on('connect_error', startFallbackPolling);

      socket.on('round_pairing_updated', function (data) {
        if (!isSameScope(data)) return;
        if (data.force_reload || !knownVersion || data.version !== knownVersion) {
          debounceReload();
        }
      });

      socket.on('event_pairing_updated', function (data) {
        if (hasRound) return;
        if (!isSameScope(data)) return;
        if (data.force_reload || !knownVersion || data.version !== knownVersion) {
          debounceReload();
        }
      });
    } catch (err) {
      startFallbackPolling();
    }
  };
})();
