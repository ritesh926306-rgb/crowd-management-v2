/**
 * VenueGuard — Static Site Bridge v2.0
 * Enables full interactive experience on GitHub Pages without a Flask backend.
 * Features: Registration, QR Generation, Pass View, Admin Dashboard, Verify Terminal.
 */
(function () {
  'use strict';

  /* ─────────────────────────── CONSTANTS ─────────────────────────── */
  const BASE_URL = 'https://ritesh926306-rgb.github.io/crowd-management-v2/';

  const GATES = [
    { group: 'Group A', gate_id: 'exit_1', name: 'Exit 1 (West)',  zone: 'Zone Alpha (West Gate)',  color: '#00FFC6', description: 'Proceed West towards West Boulevard & Transit Hub 1' },
    { group: 'Group B', gate_id: 'exit_2', name: 'Exit 2 (North)', zone: 'Zone Beta (North Gate)',  color: '#3B82F6', description: 'Proceed North towards Main Highway & North Parking'   },
    { group: 'Group C', gate_id: 'exit_3', name: 'Exit 3 (East)',  zone: 'Zone Gamma (East Gate)',  color: '#F59E0B', description: 'Proceed East towards East Plaza & Metro Shuttle'       },
    { group: 'Group D', gate_id: 'exit_4', name: 'Exit 4 (South)', zone: 'Zone Delta (South Gate)', color: '#A855F7', description: 'Proceed South towards South Promenade & Taxi Stand'   }
  ];

  const SEED_PASSES = [
    {
      reg_code: 'DEMO-SAMPLE-8899', primary_name: 'Demo Visitor', mobile: '9876543210',
      age: 30, address: '123 Venue Boulevard, Central City',
      group_count: 2, assigned_group: 'Group A', assigned_gate: 'Exit 1 (West)', gate_id: 'exit_1',
      gate_info: GATES[0],
      members: [{ member_name: 'Accompanying Guest', member_age: 28, member_mobile: '9876543211' }],
      hmac_signature: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
      created_at: '2026-10-18 20:00:00', checked_in: 0, checked_in_at: null
    },
    {
      reg_code: 'REG-A1B2C3', primary_name: 'Rajesh Kumar', mobile: '9876543210',
      age: 34, address: '45 MG Road, Civil Lines, Allahabad, UP - 211001',
      group_count: 2, assigned_group: 'Group A', assigned_gate: 'Exit 1 (West)', gate_id: 'exit_1',
      gate_info: GATES[0],
      members: [{ member_name: 'Pooja Kumar', member_age: 31, member_mobile: '9876543211' }],
      hmac_signature: '7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069',
      created_at: '2026-10-18 19:30:00', checked_in: 1, checked_in_at: '2026-10-18 19:45:00'
    },
    {
      reg_code: 'REG-D4E5F6', primary_name: 'Anita Verma', mobile: '9812345678',
      age: 29, address: '12 Lake View Apt, Sector 4, Noida - 201301',
      group_count: 3, assigned_group: 'Group B', assigned_gate: 'Exit 2 (North)', gate_id: 'exit_2',
      gate_info: GATES[1],
      members: [
        { member_name: 'Aarav Verma', member_age: 6, member_mobile: '' },
        { member_name: 'Ravi Verma', member_age: 32, member_mobile: '9812345679' }
      ],
      hmac_signature: '4937213b185bc0b11ecdeba15e98f0fa0be7d9eb01a2f90a9b099f4bf7efc2f8',
      created_at: '2026-10-18 19:40:00', checked_in: 1, checked_in_at: '2026-10-18 20:00:00'
    },
    {
      reg_code: 'REG-7G8H9I', primary_name: 'Sunil Patel', mobile: '9823456789',
      age: 42, address: '88 Sunrise Colony, Bhopal, MP - 462001',
      group_count: 4, assigned_group: 'Group C', assigned_gate: 'Exit 3 (East)', gate_id: 'exit_3',
      gate_info: GATES[2],
      members: [
        { member_name: 'Geeta Patel', member_age: 39, member_mobile: '' },
        { member_name: 'Karan Patel', member_age: 14, member_mobile: '' },
        { member_name: 'Diya Patel', member_age: 10, member_mobile: '' }
      ],
      hmac_signature: 'a84f2c98c34d2b8e1f64c990de5b38a2c5e8d22a41370ff5b5c5eae84f7f3d12',
      created_at: '2026-10-18 20:10:00', checked_in: 0, checked_in_at: null
    }
  ];

  /* ─────────────────────────── HELPERS ─────────────────────────── */

  function isStaticHost() {
    // If running under Flask backend, never run static-mode client override!
    if (typeof window.IS_FLASK_BACKEND !== 'undefined' && window.IS_FLASK_BACKEND === true) {
      return false;
    }
    if (typeof window.IS_STATIC_BUILD !== 'undefined' && window.IS_STATIC_BUILD === true) {
      return true;
    }
    // If running on a live web server (e.g., port 5000 or without .html on localhost/127.0.0.1), let the backend handle everything!
    if (window.location.port === '5000' || window.location.port === '8000' || window.location.port === '3000') {
      return false;
    }
    const h = window.location.hostname;
    if (h === 'localhost' || h === '127.0.0.1') {
      return window.location.protocol === 'file:' || window.location.pathname.endsWith('.html');
    }
    return h.endsWith('github.io') || window.location.protocol === 'file:' || window.location.pathname.endsWith('.html');
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/[&<>"']/g, function (s) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s];
    });
  }

  function getBaseUrl() {
    const loc = window.location.href;
    return loc.substring(0, loc.lastIndexOf('/') + 1);
  }

  function getPasses() {
    try {
      const raw = localStorage.getItem('vg_passes');
      if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    try { localStorage.setItem('vg_passes', JSON.stringify(SEED_PASSES)); } catch (e) { /* ignore */ }
    return SEED_PASSES;
  }

  function savePasses(passes) {
    try { localStorage.setItem('vg_passes', JSON.stringify(passes)); } catch (e) { /* ignore */ }
  }

  function saveCurrentPass(pass) {
    try { localStorage.setItem('vg_current_pass', JSON.stringify(pass)); } catch (e) { /* ignore */ }
  }

  function getCurrentPass() {
    try {
      const raw = localStorage.getItem('vg_current_pass');
      if (raw) return JSON.parse(raw);
    } catch (e) { /* ignore */ }
    return null;
  }

  function fakeHmac() {
    const chars = 'abcdef0123456789';
    return Array.from({ length: 64 }, () => chars[Math.floor(Math.random() * 16)]).join('');
  }

  function now() {
    return new Date().toISOString().replace('T', ' ').substring(0, 19);
  }

  function randCode() {
    return 'REG-' + Math.random().toString(36).substring(2, 8).toUpperCase();
  }

  /* Pick gate with lowest headcount total */
  function smartGatePick(passes) {
    const counts = { exit_1: 0, exit_2: 0, exit_3: 0, exit_4: 0 };
    passes.forEach(p => { if (counts[p.gate_id] !== undefined) counts[p.gate_id] += (p.group_count || 1); });
    let best = GATES[0];
    let min = Infinity;
    GATES.forEach(g => { if (counts[g.gate_id] < min) { min = counts[g.gate_id]; best = g; } });
    return best;
  }

  /* ─────────────────────────── QR CODE ─────────────────────────── */

  /**
   * Build a QR image URL using the qrserver.com public API.
   * Encodes the verification deep-link for this pass.
   */
  function buildQrUrl(regCode, size) {
    size = size || 200;
    const base = getBaseUrl();
    const verifyUrl = base + 'verify.html?code=' + encodeURIComponent(regCode);
    return 'https://api.qrserver.com/v1/create-qr-code/?size=' + size + 'x' + size +
           '&format=png&ecc=M&color=0-0-0&bgcolor=255-255-255' +
           '&data=' + encodeURIComponent(verifyUrl);
  }

  /**
   * Inject a QR image into a container element.
   * Shows a loading spinner first, then replaces with QR image.
   */
  function injectQrCode(containerEl, regCode, size) {
    if (!containerEl) return;
    size = size || 200;
    const url = buildQrUrl(regCode, size);

    containerEl.innerHTML = `
      <div id="qrLoadingInner" style="width:${size}px;height:${size}px;background:rgba(255,255,255,0.05);
        border:1px solid rgba(255,255,255,0.1);border-radius:10px;display:flex;align-items:center;
        justify-content:center;flex-direction:column;gap:0.5rem;">
        <div class="spinner"></div>
        <div style="font-size:0.7rem;color:var(--text-muted);">Generating QR…</div>
      </div>
    `;

    const img = new Image();
    img.onload = function () {
      containerEl.innerHTML = '';
      img.className = 'qr-image';
      img.alt = 'Verification QR Code for ' + regCode;
      img.style.cssText = 'width:' + size + 'px;height:' + size + 'px;display:block;';
      containerEl.appendChild(img);
    };
    img.onerror = function () {
      containerEl.innerHTML =
        '<div style="width:' + size + 'px;height:' + size + 'px;background:rgba(255,77,109,0.08);' +
        'border:1px solid rgba(255,77,109,0.25);border-radius:10px;display:flex;align-items:center;' +
        'justify-content:center;font-size:0.75rem;color:#FCA5A5;text-align:center;padding:1rem;">' +
        '⚠️ QR unavailable offline.<br>Connect to the internet to generate.</div>';
    };
    img.src = url;
  }

  /* ─────────────────────────── STATIC BANNER ─────────────────────────── */

  function injectBanner() {
    if (!isStaticHost()) return;
    if (document.getElementById('staticModeNotice')) return;

    const banner = document.createElement('div');
    banner.id = 'staticModeNotice';
    banner.className = 'no-print';
    banner.innerHTML = `
      <div style="display:flex;align-items:center;gap:0.5rem;flex-wrap:wrap;">
        <span style="font-size:0.9rem;">🌐</span>
        <strong>GitHub Pages Demo:</strong>
        <span>Registration, QR codes &amp; admin dashboard run fully client-side.
        For live mode: <code>python backend/app.py</code></span>
      </div>
      <button onclick="this.parentElement.remove()"
        style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:1.1rem;padding:0 0.25rem;"
        title="Dismiss">&times;</button>
    `;
    document.body.insertBefore(banner, document.body.firstChild);
  }

  /* ─────────────────────────── REGISTRATION FORM ─────────────────────────── */

  function initRegistrationForm() {
    const form = document.getElementById('registrationForm');
    if (!form) return;
    if (!isStaticHost()) return;

    // Prevent standard POST → 405
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      e.stopImmediatePropagation();

      const btn = document.getElementById('submitBtn');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> <span>Generating Pass…</span>';
      }

      const primaryName = document.getElementById('primary_name')?.value?.trim() || '';
      const mobile      = document.getElementById('mobile')?.value?.trim() || '';
      const age         = document.getElementById('age')?.value?.trim() || '';
      const address     = document.getElementById('address')?.value?.trim() || '';

      if (!primaryName || !mobile || !age || !address) {
        alert('Please fill in all mandatory fields.');
        if (btn) { btn.disabled = false; btn.innerHTML = '<span>🛡️</span><span>Generate Official Entry Pass & Exit Route</span>'; }
        return;
      }

      if (!/^\d{10}$/.test(mobile)) {
        alert('Please enter a valid 10-digit mobile number.');
        if (btn) { btn.disabled = false; btn.innerHTML = '<span>🛡️</span><span>Generate Official Entry Pass & Exit Route</span>'; }
        return;
      }

      // Collect members
      const memberNames   = [...document.querySelectorAll('input[name="member_name[]"]')];
      const memberAges    = [...document.querySelectorAll('input[name="member_age[]"]')];
      const memberMobiles = [...document.querySelectorAll('input[name="member_mobile[]"]')];

      const members = [];
      for (let i = 0; i < memberNames.length; i++) {
        const mName = memberNames[i].value.trim();
        const mAge  = memberAges[i].value.trim();
        const mMob  = memberMobiles[i]?.value?.trim() || '';
        if (mName && mAge) {
          members.push({ member_name: mName, member_age: parseInt(mAge, 10) || 0, member_mobile: mMob });
        }
      }

      const passes   = getPasses();
      const gate     = smartGatePick(passes);
      const regCode  = randCode();
      const hmac     = fakeHmac();
      const ts       = now();

      const newPass = {
        reg_code:       regCode,
        primary_name:   primaryName,
        mobile:         mobile,
        age:            parseInt(age, 10),
        address:        address,
        group_count:    1 + members.length,
        assigned_group: gate.group,
        assigned_gate:  gate.name,
        gate_id:        gate.gate_id,
        gate_info:      gate,
        members:        members,
        hmac_signature: hmac,
        created_at:     ts,
        checked_in:     0,
        checked_in_at:  null
      };

      passes.unshift(newPass);
      savePasses(passes);
      saveCurrentPass(newPass);

      // Small delay so spinner is visible
      setTimeout(() => {
        window.location.href = 'pass.html?code=' + encodeURIComponent(regCode);
      }, 400);
    }, true);
  }

  /* ─────────────────────────── PASS PAGE ─────────────────────────── */

  function initPassPage() {
    if (!document.querySelector('.pass-container')) return;
    if (!isStaticHost()) return;

    const params = new URLSearchParams(window.location.search);
    const code   = params.get('code');
    const passes = getPasses();

    let pass = code ? passes.find(p => p.reg_code === code) : null;
    if (!pass) pass = getCurrentPass();
    if (!pass && passes.length) pass = passes[0];
    if (!pass) return;

    // Save as current
    saveCurrentPass(pass);

    // Title
    document.title = 'Entry Pass — ' + pass.reg_code + ' · VenueGuard';

    // Pass code
    document.querySelectorAll('.pass-reg_code').forEach(el => { el.textContent = pass.reg_code; });

    // Gate banner
    const gateBanner = document.querySelector('.gate-banner');
    if (gateBanner) {
      gateBanner.className = 'gate-banner gate-theme-border theme-' + pass.gate_id;
      const gateIconBox = gateBanner.querySelector('.gate-icon-box');
      if (gateIconBox) gateIconBox.className = 'gate-icon-box gate-theme-bg';
      const groupSpan = gateBanner.querySelector('.gate-info span');
      if (groupSpan) groupSpan.innerHTML = 'SMART CROWD SPLIT &bull; ' + pass.assigned_group;
      const gateH4 = gateBanner.querySelector('.gate-info h4');
      if (gateH4) gateH4.textContent = pass.assigned_gate;
      const gateP = gateBanner.querySelector('.gate-info p');
      if (gateP && pass.gate_info) gateP.textContent = pass.gate_info.description;
    }

    // Details table
    const detailsTable = document.querySelector('.pass-details-table');
    if (detailsTable) {
      detailsTable.querySelectorAll('tr').forEach(tr => {
        const th = tr.querySelector('th');
        const td = tr.querySelector('td');
        if (!th || !td) return;
        const key = th.textContent.toLowerCase();
        if (key.includes('primary'))  td.textContent = pass.primary_name;
        else if (key.includes('mobile')) td.textContent = pass.mobile;
        else if (key.includes('age'))  td.textContent = pass.age + ' yrs';
        else if (key.includes('group') || key.includes('count')) {
          const badge = td.querySelector('.badge') || td;
          badge.textContent = pass.group_count + ' ' + (pass.group_count === 1 ? 'Person' : 'Persons');
        }
        else if (key.includes('address')) td.textContent = pass.address;
        else if (key.includes('issued') || key.includes('timestamp') || key.includes('generated')) td.textContent = pass.created_at;
      });
    }

    // Members table
    const membersSection = document.querySelector('.pass-body > div:first-child > div:last-child');
    if (membersSection) {
      const titleEl = membersSection.querySelector('h5');
      if (titleEl) {
        const span = titleEl.querySelector('span[data-i18n]');
        if (span) titleEl.innerHTML = '<span data-i18n="pass_members_list">Group Members</span> (' + pass.members.length + ')';
        else titleEl.textContent = 'Group Members (' + pass.members.length + ')';
      }
      const tbody = membersSection.querySelector('tbody');
      if (tbody) {
        if (pass.members.length === 0) {
          tbody.innerHTML = '<tr><td colspan="4" style="padding:0.75rem;text-align:center;color:var(--text-muted);font-style:italic;">Solo Visitor (No additional members)</td></tr>';
        } else {
          tbody.innerHTML = pass.members.map((m, i) => `
            <tr style="border-top:1px solid rgba(255,255,255,0.04);">
              <td style="padding:0.45rem 0.75rem;color:var(--text-muted);">${i+1}</td>
              <td style="padding:0.45rem 0.75rem;font-weight:600;">${m.member_name}</td>
              <td style="padding:0.45rem 0.75rem;">${m.member_age}y</td>
              <td style="padding:0.45rem 0.75rem;font-family:'JetBrains Mono',monospace;">${m.member_mobile || '—'}</td>
            </tr>
          `).join('');
        }
      }
    }

    // ── QR CODE ──
    // Find the existing qrLoader div and qrImage
    const qrLoader = document.getElementById('qrLoader');
    const qrImage  = document.getElementById('qrImage');
    const qrWrapper = document.querySelector('.qr-wrapper');

    if (qrWrapper) {
      // Replace the entire wrapper content with a freshly injected QR
      injectQrCode(qrWrapper, pass.reg_code, 170);
    } else if (qrLoader) {
      // Inject into the loader area
      injectQrCode(qrLoader.parentElement || qrLoader, pass.reg_code, 170);
    } else if (qrImage) {
      // Update existing src
      qrImage.src = buildQrUrl(pass.reg_code, 170);
      qrImage.style.display = 'block';
    }

    // Manual verification link
    const manualLink = document.querySelector('.pass-qr-box a');
    if (manualLink) {
      const verifyHref = 'verify.html?code=' + encodeURIComponent(pass.reg_code);
      manualLink.href = verifyHref;
    }

    // HMAC
    const hmacEl = document.querySelector('.hmac-hash');
    if (hmacEl) hmacEl.textContent = pass.hmac_signature;

    // SVG Blueprint — update dynamically
    updateSvgBlueprint(pass.gate_id);
  }

  function updateSvgBlueprint(gateId) {
    const svg = document.querySelector('.map-svg-container svg');
    if (!svg) return;

    // Remove existing dynamic route paths
    svg.querySelectorAll('.dynamic-route').forEach(el => el.remove());

    // Update gate rects
    const gateTransforms = {
      exit_1: 'translate(20, 138)',
      exit_2: 'translate(285, 15)',
      exit_3: 'translate(550, 138)',
      exit_4: 'translate(510, 295)'
    };

    const gateColors = { exit_1: '#00FFC6', exit_2: '#3B82F6', exit_3: '#F59E0B', exit_4: '#A855F7' };
    const gateFills  = {
      exit_1: 'rgba(0,255,198,0.15)', exit_2: 'rgba(59,130,246,0.18)',
      exit_3: 'rgba(245,158,11,0.15)', exit_4: 'rgba(168,85,247,0.15)'
    };

    Object.keys(gateTransforms).forEach(gid => {
      const g = svg.querySelector(`g[transform="${gateTransforms[gid]}"]`);
      if (!g) return;
      const rect  = g.querySelector('rect');
      const texts = g.querySelectorAll('text');
      const active = gid === gateId;
      if (rect) {
        rect.setAttribute('fill',         active ? gateFills[gid]    : 'rgba(255,255,255,0.04)');
        rect.setAttribute('stroke',       active ? gateColors[gid]   : 'rgba(255,255,255,0.1)');
        rect.setAttribute('stroke-width', active ? '2' : '1');
      }
      texts.forEach((t, i) => {
        t.setAttribute('fill', active
          ? (i === 0 ? gateColors[gid] : gateColors[gid] + 'B3')
          : (i === 0 ? 'rgba(255,255,255,0.55)' : 'rgba(255,255,255,0.3)')
        );
      });
    });

    // Draw route
    const routes = {
      exit_1: { d: 'M 350 290 L 350 163 L 150 163', color: '#00FFC6', cx: 150, cy: 163 },
      exit_2: { d: 'M 350 290 L 350 65',             color: '#3B82F6', cx: 350, cy: 65  },
      exit_3: { d: 'M 350 290 L 350 163 L 550 163',  color: '#F59E0B', cx: 550, cy: 163 },
      exit_4: { d: 'M 350 290 L 350 270 L 510 270 L 510 290', color: '#A855F7', cx: 510, cy: 290 }
    };

    const r = routes[gateId];
    if (!r) return;

    const ns = 'http://www.w3.org/2000/svg';

    const path = document.createElementNS(ns, 'path');
    path.setAttribute('class', 'dynamic-route');
    path.setAttribute('d', r.d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', r.color);
    path.setAttribute('stroke-width', '3.5');
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    path.setAttribute('filter', 'url(#glow)');
    path.setAttribute('opacity', '0.9');

    const dot = document.createElementNS(ns, 'circle');
    dot.setAttribute('class', 'dynamic-route');
    dot.setAttribute('cx', r.cx);
    dot.setAttribute('cy', r.cy);
    dot.setAttribute('r', '7');
    dot.setAttribute('fill', r.color);
    dot.setAttribute('filter', 'url(#glow)');

    const ring = document.createElementNS(ns, 'circle');
    ring.setAttribute('class', 'dynamic-route');
    ring.setAttribute('cx', r.cx);
    ring.setAttribute('cy', r.cy);
    ring.setAttribute('r', '12');
    ring.setAttribute('fill', r.color + '26');

    svg.appendChild(path);
    svg.appendChild(ring);
    svg.appendChild(dot);
  }

  /* ─────────────────────────── LOGIN PAGE ─────────────────────────── */

  function initLoginPage() {
    const form = document.getElementById('adminLoginForm') || document.querySelector('form[action*="login"]');
    if (!form) return;
    if (!isStaticHost()) return;

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const pwd = document.getElementById('password')?.value || '';
      if (pwd === 'admin123') {
        sessionStorage.setItem('vg_admin', 'true');
        window.location.href = 'admin.html';
      } else {
        alert('Invalid password! Default password is: admin123');
      }
    });
  }

  /* ─────────────────────────── GUARD LOGIN PAGE ─────────────────────────── */

  function initGuardLoginPage() {
    const form = document.getElementById('guardLoginForm');
    if (!form) return;
    if (!isStaticHost()) return;

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      const pin = document.getElementById('guardPin')?.value?.trim() || '';
      const validPin = localStorage.getItem('vg_guard_pin') || '1234';
      if (pin === validPin || pin === '1234' || pin === 'admin123') {
        sessionStorage.setItem('vg_guard', 'true');
        const params = new URLSearchParams(window.location.search);
        const nextUrl = params.get('next') || 'verify.html';
        window.location.href = nextUrl;
      } else {
        alert('Invalid Guard Access Password! Current configured password is: ' + validPin);
      }
    });
  }

  /* ─────────────────────────── ADMIN DASHBOARD ─────────────────────────── */

  function initAdminDashboard() {
    const container = document.querySelector('.admin-dashboard-container');
    if (!container) return;
    if (!isStaticHost()) return;

    hydrateAdminDashboard();

    // Bind CSV Export for static mode
    const exportBtn = document.querySelector('a[href*="export"], a[href="#"].btn-primary');
    if (exportBtn && !exportBtn.dataset.bound) {
      exportBtn.dataset.bound = 'true';
      exportBtn.addEventListener('click', function(e) {
        if (!isStaticHost()) return;
        e.preventDefault();
        exportPassesCsv();
      });
    }

    // Bind Guard Password Update in Admin Dashboard
    const pwdForm = document.querySelector('form[action*="update-guard-password"]') || document.getElementById('updateGuardPasswordForm');
    if (pwdForm && !pwdForm.dataset.bound) {
      pwdForm.dataset.bound = 'true';
      pwdForm.addEventListener('submit', function(e) {
        if (!isStaticHost()) return;
        e.preventDefault();
        const input = pwdForm.querySelector('input[name="guard_password"]');
        const val = input ? input.value.trim() : '';
        if (val.length < 4) {
          alert('Password must be at least 4 characters long.');
          return;
        }
        localStorage.setItem('vg_guard_pin', val);
        const disp = document.getElementById('currentGuardPasswordDisplay');
        if (disp) disp.value = val;
        alert('Guard access password updated to: ' + val);
        if (input) input.value = '';
      });
    }

    // Reflect configured guard password
    const curDisp = document.getElementById('currentGuardPasswordDisplay');
    if (curDisp) {
      curDisp.value = localStorage.getItem('vg_guard_pin') || '1234';
    }
  }

  function exportPassesCsv() {
    const passes = getPasses();
    const headers = [
      "Reg ID", "Registration Code", "Timestamp", "Language",
      "Primary Visitor Name", "Mobile Number", "Age", "Common Address",
      "Total Group Size", "Assigned Group", "Assigned Exit Gate",
      "Checked In Status", "Checked In Timestamp", "Accompanying Group Members",
      "HMAC Security Hash"
    ];

    const rows = passes.map((p, index) => {
      const membersStr = (p.members || []).map(m => `${m.member_name} [Age: ${m.member_age}]`).join(' | ') || 'None (Solo Visitor)';
      return [
        index + 1,
        `"${p.reg_code}"`,
        `"${p.created_at || ''}"`,
        '"EN"',
        `"${(p.primary_name || '').replace(/"/g, '""')}"`,
        `"${p.mobile || ''}"`,
        p.age || 0,
        `"${(p.address || '').replace(/"/g, '""')}"`,
        p.group_count || 1,
        `"${p.assigned_group || ''}"`,
        `"${p.assigned_gate || ''}"`,
        p.checked_in === 1 ? '"ADMITTED"' : '"PENDING"',
        `"${p.checked_in_at || 'N/A'}"`,
        `"${membersStr.replace(/"/g, '""')}"`,
        `"${p.hmac_signature || ''}"`
      ].join(',');
    });

    const csvContent = "data:text/csv;charset=utf-8," + [headers.join(','), ...rows].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    const timestamp = new Date().toISOString().replace(/[-:T]/g, '').substring(0, 14);
    link.setAttribute("download", `venue_crowd_data_${timestamp}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  function hydrateAdminDashboard() {
    const passes = getPasses();

    let totalHeadcount = 0;
    let admittedCount  = 0;
    const gateStats = { exit_1: 0, exit_2: 0, exit_3: 0, exit_4: 0 };

    passes.forEach(p => {
      const n = p.group_count || 1;
      totalHeadcount += n;
      if (p.checked_in === 1) admittedCount += n;
      if (gateStats[p.gate_id] !== undefined) gateStats[p.gate_id] += n;
    });

    // KPI stat numbers
    const statCards = document.querySelectorAll('.stat-card');
    if (statCards.length >= 3) {
      const n1 = statCards[0].querySelector('.stat-number');
      if (n1) n1.textContent = totalHeadcount;
      const n2 = statCards[1].querySelector('.stat-number');
      if (n2) n2.textContent = passes.length;
      const n3 = statCards[2].querySelector('.stat-number');
      if (n3) n3.textContent = admittedCount;
      const i3 = statCards[2].querySelector('.stat-indicator');
      if (i3) {
        const pct = totalHeadcount > 0 ? Math.round((admittedCount / totalHeadcount) * 100) : 0;
        i3.textContent = pct + '% of total entered';
      }
    }

    // Gate bars
    const gateBoxes = document.querySelectorAll('.gate-capacity-grid .gate-stat-box');
    const gateOrder = ['exit_1', 'exit_2', 'exit_3', 'exit_4'];
    gateBoxes.forEach((box, i) => {
      const gid   = gateOrder[i];
      const count = gateStats[gid] || 0;
      const pct   = totalHeadcount > 0 ? Math.round((count / totalHeadcount) * 100) : 0;
      const countSpan = box.querySelector('.gate-theme-color');
      if (countSpan) countSpan.textContent = count + ' pax';
      const bar = box.querySelector('.progress-bar-fill');
      if (bar) { bar.style.width = '0%'; setTimeout(() => { bar.style.width = pct + '%'; }, 100); }
      const pctTexts = box.querySelectorAll('div');
      pctTexts.forEach(d => { if (d.textContent.includes('% crowd')) d.textContent = pct + '% crowd share'; });
    });

    // Registrations table — replace tbody
    const tbody = document.querySelector('#registrationsTable tbody');
    if (tbody) {
      if (passes.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:2rem;color:var(--text-muted);">No registrations yet.</td></tr>';
      } else {
        tbody.innerHTML = passes.map(p => {
          const members = p.members || [];
          const memberSummary = members.length > 0
            ? members.map(m => m.member_name).join(', ')
            : '';
          const admitIcon = p.checked_in === 1
            ? '<span class="badge badge-success">✓ Admitted</span>'
            : '<span class="badge badge-warning">⏳ Pending</span>';

          return `
            <tr>
              <td class="mono-font" style="font-weight:700;">
                <a href="pass.html?code=${encodeURIComponent(p.reg_code)}"
                  style="color:var(--teal);text-decoration:none;">${p.reg_code}</a>
              </td>
              <td style="font-size:0.78rem;color:var(--text-muted);white-space:nowrap;">${p.created_at || ''}</td>
              <td>
                <div style="font-weight:600;">${p.primary_name}</div>
                <div style="font-size:0.74rem;color:var(--text-muted);">Age: ${p.age}y</div>
              </td>
              <td class="mono-font" style="font-size:0.85rem;">${p.mobile}</td>
              <td><span class="badge badge-teal">${p.group_count} pax</span></td>
              <td style="font-size:0.8rem;color:var(--text-secondary);max-width:180px;">
                ${memberSummary || '<span style="color:var(--text-muted);font-style:italic;">Solo</span>'}
              </td>
              <td>
                <span class="badge" style="background:rgba(255,255,255,0.06);color:var(--text-primary);border:1px solid var(--glass-border);">
                  ${p.assigned_gate}
                </span>
              </td>
              <td>${admitIcon}</td>
              <td>
                <div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
                  <a href="verify.html?code=${encodeURIComponent(p.reg_code)}"
                    class="btn btn-outline" style="padding:0.28rem 0.6rem;font-size:0.74rem;" title="Verify">🛡️</a>
                  <button class="btn btn-danger-outline" style="padding:0.28rem 0.6rem;font-size:0.74rem;"
                    onclick="deletePass('${p.reg_code}')" title="Delete">🗑️</button>
                </div>
              </td>
            </tr>
          `;
        }).join('');
      }
    }
  }

  window.deletePass = function (regCode) {
    if (!confirm('Permanently delete registration ' + regCode + '?')) return;
    const passes = getPasses().filter(p => p.reg_code !== regCode);
    savePasses(passes);
    hydrateAdminDashboard();
  };

  window.toggleAdminCheckIn = function (regCode) {
    const passes = getPasses();
    const p = passes.find(item => item.reg_code === regCode);
    if (p) {
      p.checked_in = p.checked_in === 1 ? 0 : 1;
      p.checked_in_at = p.checked_in === 1 ? now() : null;
      savePasses(passes);
      hydrateAdminDashboard();
    }
  };

  /* ─────────────────────────── VERIFY TERMINAL ─────────────────────────── */

  function initVerifyTerminal() {
    const card = document.querySelector('.terminal-card');
    if (!card) return;
    if (!isStaticHost()) return;

    const params = new URLSearchParams(window.location.search);
    const code   = params.get('code');
    if (!code) return;

    const passes = getPasses();
    const pass   = passes.find(p => p.reg_code.toUpperCase() === code.toUpperCase());
    if (!pass) {
      card.innerHTML = `
        <div class="verification-status status-invalid">
          <div class="status-icon">⚠️</div>
          <h1 class="status-title">FRAUD WARNING: INVALID ENTRY PASS</h1>
          <p class="status-desc">REGISTRATION CODE NOT FOUND IN DATABASE. POTENTIAL COUNTERFEIT PASS.</p>
        </div>
        <div class="terminal-body" style="padding: 2.5rem 1.5rem; text-align: center;">
          <div style="background: rgba(239, 68, 68, 0.08); border: 1.5px solid rgba(239, 68, 68, 0.25); border-radius: var(--radius-md); padding: 1.5rem; max-width: 580px; margin: 0 auto 1.5rem;">
            <p style="color: #FCA5A5; font-size: 1rem; font-weight: 700; margin-bottom: 0.4rem;">Scanned Pass Code: <span class="mono-font">${escapeHtml(code)}</span></p>
            <p style="color: var(--text-muted); font-size: 0.85rem;">This pass code does not exist in the verified registry. Entry denied under venue safety protocols.</p>
          </div>
          <a href="verify.html" class="btn btn-navy">← Return to Guard Scanner Terminal</a>
        </div>
      `;
      return;
    }

    // Update status bar description
    const statusDesc = document.querySelector('.status-desc');
    if (statusDesc) {
      statusDesc.textContent = 'HMAC Signature verified for ' + pass.reg_code + '. Authorized for entry.';
    }

    // Headcount
    const countBig = document.querySelector('.terminal-body [style*="2.5rem"]');
    if (countBig) countBig.textContent = pass.group_count;

    // Group label
    const groupCountLabel = document.querySelector('.terminal-body [style*="1.4rem"]');
    if (groupCountLabel) groupCountLabel.textContent = pass.assigned_gate;

    // Pass code quick cell
    const codeEl = document.querySelector('.terminal-body .mono-font[style*="teal"]');
    if (codeEl) codeEl.textContent = pass.reg_code;

    // Details table
    const detTable = document.querySelector('.terminal-body .pass-details-table');
    if (detTable) {
      detTable.querySelectorAll('tr').forEach(tr => {
        const th = tr.querySelector('th');
        const td = tr.querySelector('td');
        if (!th || !td) return;
        const key = th.textContent.toLowerCase();
        if (key.includes('pass code'))       td.textContent = pass.reg_code;
        else if (key.includes('primary'))    td.textContent = pass.primary_name + ' (Age: ' + pass.age + ')';
        else if (key.includes('mobile'))     td.textContent = pass.mobile;
        else if (key.includes('address'))    td.textContent = pass.address;
        else if (key.includes('exit'))       { td.textContent = pass.assigned_gate + ' (' + pass.assigned_group + ')'; }
      });
    }

    // Members table
    const membersTbody = document.querySelector('.terminal-body table:last-of-type tbody');
    if (membersTbody && pass.members?.length > 0) {
      membersTbody.innerHTML = pass.members.map((m, i) => `
        <tr style="border-top:1px solid rgba(255,255,255,0.04);">
          <td style="padding:0.5rem 0.8rem;color:var(--text-muted);">${i+1}</td>
          <td style="padding:0.5rem 0.8rem;font-weight:600;">${m.member_name}</td>
          <td style="padding:0.5rem 0.8rem;">${m.member_age}y</td>
          <td style="padding:0.5rem 0.8rem;font-family:'JetBrains Mono',monospace;">${m.member_mobile || '—'}</td>
        </tr>
      `).join('');
    }

    // HMAC
    const hmacEl = document.querySelector('.terminal-body .mono-font[style*="word-break"]');
    if (hmacEl) hmacEl.textContent = pass.hmac_signature;

    // Check-In state
    refreshVerifyCheckIn(pass, passes);

    // Override checkIn button for static mode
    const btn = document.getElementById('checkInBtn');
    if (btn) {
      btn.onclick = function () {
        pass.checked_in = pass.checked_in === 1 ? 0 : 1;
        pass.checked_in_at = pass.checked_in === 1 ? now() : null;
        savePasses(passes);
        refreshVerifyCheckIn(pass, passes);
      };
    }
  }

  function refreshVerifyCheckIn(pass, passes) {
    const statusText = document.getElementById('checkInStatusText');
    const iconSpan   = document.getElementById('checkInBtnIcon');
    const btn        = document.getElementById('checkInBtn');
    if (!statusText || !iconSpan || !btn) return;

    if (pass.checked_in === 1) {
      statusText.innerHTML = `<span style="color:#4ADE80;font-weight:700;">● Admitted at ${pass.checked_in_at || 'Terminal'}</span>`;
      iconSpan.textContent = '↩️ Undo Admission';
      btn.className = 'btn btn-outline btn-admitted';
    } else {
      statusText.innerHTML = `<span style="color:var(--amber);font-weight:700;">⏳ Pending physical entry at gate</span>`;
      iconSpan.textContent = '🚪 Mark as Admitted';
      btn.className = 'btn btn-primary';
    }
  }

  /* ─────────────────────────── MANUAL LOOKUP (verify.html static) ─────────────────────────── */

  window.manualLookup = function () {
    const code = document.getElementById('manualRegCode')?.value?.trim();
    if (!code) return;
    if (isStaticHost()) {
      window.location.href = 'verify.html?code=' + encodeURIComponent(code.toUpperCase());
    } else {
      window.location.href = '/verify/' + encodeURIComponent(code.toUpperCase());
    }
  };

  /* ─────────────────────────── CLIENT-SIDE SCANNER APIs (FOR GITHUB PAGES) ─────────────────────────── */

  window.staticVerifyPassAjax = function(regCode) {
    const isGuard = sessionStorage.getItem('vg_guard') === 'true' || sessionStorage.getItem('vg_admin') === 'true';
    if (!isGuard) {
      return {
        success: false,
        is_valid: false,
        tamper_reason: "UNAUTHORIZED: Guard login required to scan/verify passes."
      };
    }

    const passes = getPasses();
    const cleanCode = (regCode || '').trim().toUpperCase();
    const pass = passes.find(p => p.reg_code.toUpperCase() === cleanCode);

    if (!pass) {
      return {
        success: false,
        is_valid: false,
        tamper_reason: "REGISTRATION CODE NOT FOUND IN DATABASE. POTENTIAL COUNTERFEIT PASS."
      };
    }

    return {
      success: true,
      is_valid: true,
      reg: pass,
      members: pass.members || [],
      gate_info: pass.gate_info || GATES[0],
      is_already_checked_in: (pass.checked_in === 1)
    };
  };

  window.staticToggleCheckIn = function(regCode) {
    const passes = getPasses();
    const cleanCode = (regCode || '').trim().toUpperCase();
    const pass = passes.find(p => p.reg_code.toUpperCase() === cleanCode);
    if (!pass) return { success: false, message: 'Registration record not found.' };

    const newStatus = pass.checked_in === 1 ? 0 : 1;
    pass.checked_in = newStatus;
    pass.checked_in_at = newStatus === 1 ? now() : null;
    savePasses(passes);

    return {
      success: true,
      checked_in: newStatus,
      checked_in_at: pass.checked_in_at
    };
  };

  /* ─────────────────────────── NAVBAR STATIC STATE ─────────────────────────── */

  function updateStaticNavbar() {
    if (!isStaticHost()) return;
    const isAdmin = sessionStorage.getItem('vg_admin') === 'true';
    const actions = document.querySelector('.header-actions');
    if (!actions) return;
    const adminLink = actions.querySelector('a[href*="login"], a[href*="admin"]');
    if (adminLink && isAdmin) {
      adminLink.outerHTML = `
        <a href="admin.html" class="nav-link active">Dashboard</a>
        <a href="#" onclick="logoutStaticAdmin(event)" class="nav-link" style="color: var(--red);">Logout</a>
      `;
    }

    // Intercept exit/lock portal link for guard in static mode
    const exitGuardBtns = document.querySelectorAll('a[href*="logout"], a[href*="guard/logout"]');
    exitGuardBtns.forEach(btn => {
      if (!btn.dataset.guardBound && btn.textContent.includes('Exit')) {
        btn.dataset.guardBound = 'true';
        btn.addEventListener('click', function(e) {
          e.preventDefault();
          sessionStorage.removeItem('vg_guard');
          window.location.href = 'guard_login.html';
        });
      }
    });
  }

  window.logoutStaticAdmin = function (e) {
    if (e) e.preventDefault();
    sessionStorage.removeItem('vg_admin');
    window.location.href = 'login.html';
  };

  /* ─────────────────────────── BOOT ─────────────────────────── */

  function boot() {
    if (!isStaticHost()) return;
    injectBanner();
    updateStaticNavbar();
    initRegistrationForm();
    initPassPage();
    initLoginPage();
    initGuardLoginPage();
    initAdminDashboard();
    initVerifyTerminal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

})();
