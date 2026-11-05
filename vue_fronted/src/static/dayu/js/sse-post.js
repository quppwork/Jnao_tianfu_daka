/**
 * 静态 HTML 复用的 POST + SSE 读取器（与 vue_fronted/src/utils/api/client.js 的 streamPostSse 对齐）。
 * 只管协议：token / replace / status / done / error / [DONE]；渲染与鉴权头由调用页提供。
 *
 * JnaoSse.post(url, { headers, body, signal }, { onToken, onReplace, onStatus, onDone })
 *   → Promise<done 事件对象 | null>；error 事件与非 2xx 会 reject（Error.message 为可展示文案）。
 */
(function (global) {
  'use strict';

  function post(url, opts, handlers) {
    opts = opts || {};
    handlers = handlers || {};
    var headers = Object.assign(
      { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      opts.headers || {}
    );
    return fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(opts.body || {}),
      signal: opts.signal,
      credentials: 'same-origin',
    }).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          var detail = data.detail || data.message;
          throw new Error(typeof detail === 'string' && detail ? detail : '请求失败 ' + res.status);
        });
      }
      var reader = res.body && res.body.getReader();
      if (!reader) throw new Error('流式响应不可用');
      var decoder = new TextDecoder();
      var buffer = '';
      var finalEvt = null;

      function dispatch(evt) {
        if (evt.type === 'token' && evt.content) {
          if (handlers.onToken) handlers.onToken(evt.content, evt);
        } else if (evt.type === 'replace') {
          if (handlers.onReplace) handlers.onReplace(evt.content || '', evt);
        } else if (evt.type === 'status' && (evt.message || evt.content)) {
          if (handlers.onStatus) handlers.onStatus(evt.message || evt.content, evt);
        } else if (evt.type === 'done') {
          finalEvt = evt;
          if (handlers.onDone) handlers.onDone(evt);
        } else if (evt.type === 'error') {
          throw new Error(evt.message || '流式请求失败');
        }
      }

      function pump() {
        return reader.read().then(function (chunk) {
          if (chunk.done) return finalEvt;
          buffer += decoder.decode(chunk.value, { stream: true });
          var sep;
          while ((sep = buffer.indexOf('\n\n')) >= 0) {
            var block = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            var line = block.split('\n').find(function (l) { return l.indexOf('data: ') === 0; });
            if (!line) continue;
            var raw = line.slice(6).trim();
            if (raw === '[DONE]') continue;
            var evt;
            try { evt = JSON.parse(raw); } catch (e) { evt = { type: 'token', content: raw }; }
            dispatch(evt);
          }
          return pump();
        });
      }
      return pump();
    });
  }

  global.JnaoSse = { post: post };
})(window);
