// ==UserScript==
// @name         STV Scraper Custom Range v1.9.2
// @namespace    http://tampermonkey.net/
// @version      1.9.2
// @description  Cào truyện STV - Fix lỗi âm thanh bằng Web Audio API
// @author       ChatGPT & Đạt
// @match        *://sangtacviet.com/truyen/*
// @match        *://*.sangtacviet.com/truyen/*
// @run-at       document-idle
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_addStyle
// ==/UserScript==

(function() {
    'use strict';

    // HÀM TẠO TIẾNG BEEP BẰNG WEB AUDIO API (Không cần file mp3/wav)
    function playBeep(duration = 200, frequency = 440, volume = 0.1) {
        try {
            const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioCtx.createOscillator();
            const gainNode = audioCtx.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(audioCtx.destination);

            oscillator.type = 'sine'; // Kiểu sóng hình sin
            oscillator.frequency.setValueAtTime(frequency, audioCtx.currentTime); 
            gainNode.gain.setValueAtTime(volume, audioCtx.currentTime);

            oscillator.start();
            oscillator.stop(audioCtx.currentTime + (duration / 1000));
        } catch (e) {
            console.error("Không thể phát âm thanh: ", e);
        }
    }

    GM_addStyle("body { border: 4px solid #9b59b6 !important; }");

    const KEY_DATA = 'stv_data_v19';
    const KEY_CONFIG = 'stv_config_v19';

    function createUI() {
        if (document.getElementById('stv-ui-v19')) return;

        let config = GM_getValue(KEY_CONFIG, { isRunning: false, target: 0, current: 0 });

        const ui = document.createElement('div');
        ui.id = 'stv-ui-v19';
        ui.setAttribute('style', `
            position: fixed; bottom: 20px; right: 20px; z-index: 9999999;
            background: #2c3e50; color: white; padding: 20px;
            border-radius: 12px; box-shadow: 0 0 25px rgba(0,0,0,0.6);
            font-family: sans-serif; border: 2px solid #9b59b6; width: 220px;
        `);

        ui.innerHTML = `
            <b style="color:#9b59b6; font-size:16px;">STV AUTO v1.9.2</b><br>
            <div id="stv-status" style="font-size:12px; margin:10px 0; color:#bdc3c7;">
                ${config.isRunning ? `🔄 Đang chạy: ${config.current}/${config.target}` : "Chế độ chờ..."}
            </div>

            ${!config.isRunning ? `
                <div style="margin-bottom:10px;">
                    <label style="font-size:11px;">Số chương muốn cào:</label><br>
                    <input type="number" id="stv-input-limit" value="10" style="width:100%; padding:5px; margin-top:5px; border-radius:4px; border:none; color:black;">
                </div>
                <button id="stv-test-sound" style="width:100%; background:#555; color:white; border:none; padding:5px; cursor:pointer; border-radius:5px; font-size:10px; margin-bottom:5px;">🔊 BẤM ĐỂ THỬ TIẾNG</button>
                <button id="stv-start" style="width:100%; background:#9b59b6; color:white; border:none; padding:10px; cursor:pointer; border-radius:5px; font-weight:bold;">BẮT ĐẦU CÀO</button>
            ` : `
                <button id="stv-stop" style="width:100%; background:#e67e22; color:white; border:none; padding:10px; cursor:pointer; border-radius:5px; font-weight:bold;">DỪNG LẠI</button>
            `}

            <div style="display:flex; gap:5px; margin-top:10px;">
                <button id="stv-dl" style="flex:1; background:#27ae60; color:white; border:none; padding:8px; cursor:pointer; border-radius:5px; font-size:12px;">TẢI FILE</button>
                <button id="stv-del" style="flex:0.5; background:#c0392b; color:white; border:none; padding:8px; cursor:pointer; border-radius:5px; font-size:12px;">XÓA</button>
            </div>
        `;

        document.body.appendChild(ui);

        document.getElementById('stv-test-sound')?.addEventListener('click', () => {
            playBeep(300, 660, 0.2); // Phát tiếng Beep 300ms, tần số 660Hz
            console.log("Đã kích hoạt thử âm thanh.");
        });

        if (document.getElementById('stv-start')) {
            document.getElementById('stv-start').onclick = () => {
                let limit = parseInt(document.getElementById('stv-input-limit').value);
                if (limit > 0) {
                    GM_setValue(KEY_CONFIG, { isRunning: true, target: limit, current: 0 });
                    location.reload();
                }
            };
        }

        if (document.getElementById('stv-stop')) {
            document.getElementById('stv-stop').onclick = () => {
                GM_setValue(KEY_CONFIG, { isRunning: false, target: 0, current: 0 });
                location.reload();
            };
        }

        document.getElementById('stv-dl').onclick = download;
        document.getElementById('stv-del').onclick = () => { if(confirm("Xóa toàn bộ dữ liệu?")) GM_setValue(KEY_DATA, ""); };
    }

    function download() {
        const data = GM_getValue(KEY_DATA, "");
        const blob = new Blob([data], { type: 'text/plain' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'Truyen_STV_Chon_Loc.txt';
        a.click();
    }

    function scrape() {
        let config = GM_getValue(KEY_CONFIG, { isRunning: false, target: 0, current: 0 });
        if (!config.isRunning) return;

        // KIỂM TRA CAPTCHA
        const isCaptcha = document.body.innerText.includes("Verify you are human") || 
                          document.querySelector('.cf-turnstile, #cf-turnstile-wrapper') ||
                          document.body.innerText.includes("Captcha");

        if (isCaptcha) {
            document.getElementById('stv-status').innerText = "⚠️ ĐANG ĐỢI GIẢI CAPTCHA...";
            playBeep(500, 880, 0.3); // Tiếng Beep cảnh báo cao hơn
            setTimeout(scrape, 5000);
            return;
        }

        const boxes = document.querySelectorAll('.contentbox[id^="cld-"]');
        if (boxes.length > 0) {
            let content = "";
            boxes.forEach(b => { if(b.innerText.length > 10) content += b.innerText.trim() + "\n\n"; });

            if (content.length > 50) {
                let title = document.title.split('-')[0].trim();
                let savedData = GM_getValue(KEY_DATA, "");
                GM_setValue(KEY_DATA, savedData + `\n\n=== ${title} ===\n\n` + content);

                config.current += 1;
                GM_setValue(KEY_CONFIG, config);

                if (config.current >= config.target) {
                    GM_setValue(KEY_CONFIG, { isRunning: false, target: 0, current: 0 });
                    playBeep(200, 440, 0.2);
                    setTimeout(() => playBeep(200, 554, 0.2), 250);
                    setTimeout(() => playBeep(400, 659, 0.2), 500); // Âm thanh báo hoàn thành
                    alert("✅ ĐÃ HOÀN THÀNH!");
                    location.reload();
                } else {
                    setTimeout(() => {
                        let next = document.querySelector('a.btn-next, a[href*="chuong-sau"], .btn-next-chap');
                        if (!next) {
                            const anchors = document.querySelectorAll('a');
                            for (let a of anchors) { if (a.innerText.includes("Chương sau")) { next = a; break; } }
                        }
                        if (next) {
                            if (next.href) window.location.href = next.href; else next.click();
                        }
                    }, 4000); 
                }
            } else {
                setTimeout(scrape, 2000);
            }
        } else {
            setTimeout(scrape, 2000);
        }
    }

    window.addEventListener('load', () => {
        createUI();
        if (!document.body.innerText.includes("human")) {
            scrape();
        }
    });

})();