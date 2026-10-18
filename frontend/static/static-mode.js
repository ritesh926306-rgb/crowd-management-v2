/**
 * Venue Crowd Management System - Client-Side Bridge for GitHub Pages
 * Enables full interactive registration, smart exit gate allocation,
 * QR code rendering, and admin previews in static environments without backend server errors (405 Method Not Allowed).
 */

(function () {
  'use strict';

  // 1. Detection of Static Hosting (GitHub Pages, file://, or static deployment)
  function isStaticEnvironment() {
    return (
      window.location.hostname.endsWith('github.io') ||
      window.location.protocol === 'file:' ||
      window.location.pathname.endsWith('.html') ||
      window.location.port === '' ||
      window.location.port === '80' ||
      window.location.port === '443'
    );
  }

  window.isStaticHost = isStaticEnvironment;

  // 2. Default Gate Metadata
  const GATES = [
    {
      group: "Group A",
      gate_id: "exit_1",
      name: "Exit 1 (West)",
      zone: "Zone Alpha (West Gate)",
      color: "#00ADB5",
      description: "Proceed West towards West Boulevard & Transit Hub 1"
    },
    {
      group: "Group B",
      gate_id: "exit_2",
      name: "Exit 2 (North)",
      zone: "Zone Beta (North Gate)",
      color: "#1E3E62",
      description: "Proceed North towards Main Highway & North Parking"
    },
    {
      group: "Group C",
      gate_id: "exit_3",
      name: "Exit 3 (East)",
      zone: "Zone Gamma (East Gate)",
      color: "#D97706",
      description: "Proceed East towards East Plaza & Metro Shuttle"
    },
    {
      group: "Group D",
      gate_id: "exit_4",
      name: "Exit 4 (South)",
      zone: "Zone Delta (South Gate)",
      color: "#7C3AED",
      description: "Proceed South towards South Promenade & Taxi Stand"
    }
  ];

  // 3. Seed Passes Storage
  function getStoredPasses() {
    try {
      const raw = localStorage.getItem('venue_passes');
      if (raw) {
        return JSON.parse(raw);
      }
    } catch (e) {
      console.warn("Could not read localStorage", e);
    }
    const seed = [
      {
        reg_code: "DEMO-SAMPLE-8899",
        primary_name: "Demo Visitor",
        mobile: "9876543210",
        age: 30,
        address: "123 Venue Boulevard, Central City",
        group_count: 2,
        assigned_group: "Group A",
        assigned_gate: "Exit 1 (West)",
        gate_id: "exit_1",
        gate_info: GATES[0],
        members: [{ member_name: "Accompanying Guest", member_age: 28, member_mobile: "9876543211" }],
        hmac_signature: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        created_at: "2026-10-18 20:00:00",
        checked_in: 0
      },
      {
        reg_code: "REG-A1B2C3",
        primary_name: "Rajesh Kumar",
        mobile: "9876543210",
        age: 34,
        address: "45 MG Road, Civil Lines",
        group_count: 2,
        assigned_group: "Group A",
        assigned_gate: "Exit 1 (West)",
        gate_id: "exit_1",
        gate_info: GATES[0],
        members: [{ member_name: "Pooja Kumar", member_age: 31, member_mobile: "9876543211" }],
        hmac_signature: "7f83b1657ff1fc53b92dc18148a1d65dfc2d4b1fa3d677284addd200126d9069",
        created_at: "2026-10-18 19:30:00",
        checked_in: 1,
        checked_in_at: "2026-10-18 19:45:00"
      },
      {
        reg_code: "REG-D4E5F6",
        primary_name: "Anita Verma",
        mobile: "9812345678",
        age: 29,
        address: "12 Lake View Apartment, Sector 4",
        group_count: 3,
        assigned_group: "Group B",
        assigned_gate: "Exit 2 (North)",
        gate_id: "exit_2",
        gate_info: GATES[1],
        members: [
          { member_name: "Aarav Verma", member_age: 6, member_mobile: "" },
          { member_name: "Ravi Verma", member_age: 32, member_mobile: "9812345679" }
        ],
        hmac_signature: "4937213b185bc0b11ecdeba15e98f0fa0be7d9eb01a2f90a9b099f4bf7efc2f8",
        created_at: "2026-10-18 19:40:00",
        checked_in: 1,
        checked_in_at: "2026-10-18 20:00:00"
      }
    ];
    try {
      localStorage.setItem('venue_passes', JSON.stringify(seed));
    } catch (e) {}
    return seed;
  }

  function savePass(pass) {
    const list = getStoredPasses();
    list.unshift(pass);
    try {
      localStorage.setItem('venue_passes', JSON.stringify(list));
      localStorage.setItem('venue_current_pass', JSON.stringify(pass));
    } catch (e) {}
  }

  // 4. Banner Notice for Static Deployment
  function injectStaticBanner() {
    if (!isStaticEnvironment()) return;
    if (document.getElementById('staticModeNotice')) return;

    const banner = document.createElement('div');
    banner.id = 'staticModeNotice';
    banner.className = 'no-print';
    banner.style.cssText =
      'background: #0B192C; color: #E0F2FE; font-size: 0.82rem; padding: 0.5rem 1.25rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #00ADB5; z-index: 9999;';

    banner.innerHTML = `
      <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
        <span style="font-size: 1rem;">🌐</span>
        <strong>GitHub Pages Interactive Demo:</strong>
        <span>Registrations & dynamic QR passes run client-side in your browser. (For live Flask/MySQL server, run <code>python backend/app.py</code> locally).</span>
      </div>
      <button onclick="this.parentElement.remove()" style="background: none; border: none; color: #94A3B8; cursor: pointer; font-size: 1.1rem; line-height: 1; padding: 0 0.25rem;" title="Dismiss">&times;</button>
    `;

    document.body.insertBefore(banner, document.body.firstChild);
  }

  // 5. Intercept Registration Form on index.html
  function initRegistrationForm() {
    const form = document.getElementById('registrationForm');
    if (!form) return;

    // In static environments, change form method/action so standard submit doesn't trigger 405
    if (isStaticEnvironment()) {
      form.setAttribute('onsubmit', 'return false;');
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        e.stopPropagation();

        if (typeof window.validateForm === 'function' && !window.validateForm()) {
          return false;
        }

        const primaryName = (document.getElementById('primary_name') || {}).value?.trim();
        const mobile = (document.getElementById('mobile') || {}).value?.trim();
        const age = (document.getElementById('age') || {}).value?.trim();
        const address = (document.getElementById('address') || {}).value?.trim();

        if (!primaryName || !mobile || !age || !address) {
          alert('Please fill in all mandatory primary visitor fields.');
          return false;
        }

        // Accompanying members
        const memberNames = document.querySelectorAll('input[name="member_name[]"]');
        const memberAges = document.querySelectorAll('input[name="member_age[]"]');
        const memberMobiles = document.querySelectorAll('input[name="member_mobile[]"]');

        const members = [];
        for (let i = 0; i < memberNames.length; i++) {
          const mName = memberNames[i].value.trim();
          const mAge = memberAges[i].value.trim();
          const mMob = memberMobiles[i].value.trim();
          if (mName && mAge) {
            members.push({
              member_name: mName,
              member_age: parseInt(mAge, 10) || 0,
              member_mobile: mMob
            });
          }
        }

        // Smart Capacity Split: Pick gate with lowest count
        const passes = getStoredPasses();
        const counts = { exit_1: 0, exit_2: 0, exit_3: 0, exit_4: 0 };
        passes.forEach(p => {
          if (counts[p.gate_id] !== undefined) counts[p.gate_id] += p.group_count || 1;
        });

        let chosenGate = GATES[0];
        let minCount = Infinity;
        GATES.forEach(g => {
          if (counts[g.gate_id] < minCount) {
            minCount = counts[g.gate_id];
            chosenGate = g;
          }
        });

        const randHex = Math.random().toString(36).substring(2, 8).toUpperCase();
        const regCode = `REG-${randHex}`;
        const dateStr = new Date().toISOString().replace('T', ' ').substring(0, 19);

        // Simulated HMAC cryptographic signature
        const sigChars = 'abcdef0123456789';
        let hmacSig = '';
        for (let k = 0; k < 64; k++) {
          hmacSig += sigChars[Math.floor(Math.random() * sigChars.length)];
        }

        const newPass = {
          reg_code: regCode,
          primary_name: primaryName,
          mobile: mobile,
          age: parseInt(age, 10),
          address: address,
          group_count: 1 + members.length,
          assigned_group: chosenGate.group,
          assigned_gate: chosenGate.name,
          gate_id: chosenGate.gate_id,
          gate_info: chosenGate,
          members: members,
          hmac_signature: hmacSig,
          created_at: dateStr,
          checked_in: 0
        };

        savePass(newPass);

        // Redirect safely to pass.html
        window.location.href = `pass.html?code=${encodeURIComponent(regCode)}`;
        return false;
      });
    }
  }

  // 6. Hydrate Pass View on pass.html
  function initPassView() {
    const passContainer = document.querySelector('.pass-container');
    if (!passContainer) return;

    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');

    const passes = getStoredPasses();
    let currentPass = null;

    if (code) {
      currentPass = passes.find(p => p.reg_code === code);
    }
    if (!currentPass) {
      try {
        const rawCurrent = localStorage.getItem('venue_current_pass');
        if (rawCurrent) currentPass = JSON.parse(rawCurrent);
      } catch (e) {}
    }
    if (!currentPass && passes.length > 0) {
      currentPass = passes[0];
    }

    if (!currentPass) return;

    // Update document title
    document.title = `Official Entry Pass - ${currentPass.reg_code}`;

    // Update Pass Code
    document.querySelectorAll('.pass-reg_code').forEach(el => {
      el.textContent = currentPass.reg_code;
    });

    // Update Gate Banner
    const gateBanner = document.querySelector('.gate-banner');
    if (gateBanner) {
      gateBanner.className = `gate-banner gate-theme-border theme-${currentPass.gate_id}`;
      const groupSpan = gateBanner.querySelector('.gate-info span');
      if (groupSpan) {
        groupSpan.innerHTML = `SMART CROWD SPLIT &bull; ${currentPass.assigned_group}`;
      }
      const gateTitle = gateBanner.querySelector('.gate-info h4');
      if (gateTitle) gateTitle.textContent = currentPass.assigned_gate;
      const gateDesc = gateBanner.querySelector('.gate-info p');
      if (gateDesc && currentPass.gate_info) gateDesc.textContent = currentPass.gate_info.description;
    }

    // Update Visitor Credentials Table
    const table = document.querySelector('.pass-details-table');
    if (table) {
      const rows = table.querySelectorAll('tr');
      rows.forEach(tr => {
        const th = tr.querySelector('th');
        const td = tr.querySelector('td');
        if (!th || !td) return;
        const text = th.textContent.toLowerCase();
        if (text.includes('primary visitor')) {
          td.textContent = currentPass.primary_name;
        } else if (text.includes('mobile')) {
          td.textContent = currentPass.mobile;
        } else if (text.includes('age')) {
          td.textContent = `${currentPass.age} years`;
        } else if (text.includes('total group') || text.includes('headcount')) {
          const badge = td.querySelector('.badge') || td;
          badge.textContent = `${currentPass.group_count} ${currentPass.group_count === 1 ? 'Person' : 'Persons'}`;
        } else if (text.includes('address')) {
          td.textContent = currentPass.address;
        } else if (text.includes('generated') || text.includes('timestamp')) {
          td.textContent = currentPass.created_at;
        }
      });
    }

    // Update Members Table
    const membersContainer = document.querySelector('.pass-body > div:first-child > div:last-child');
    if (membersContainer && currentPass.members) {
      const titleEl = membersContainer.querySelector('h5');
      if (titleEl) {
        titleEl.innerHTML = `<span>Accompanying Group Members</span> (${currentPass.members.length})`;
      }
      const tbody = membersContainer.querySelector('tbody');
      if (tbody) {
        if (currentPass.members.length > 0) {
          tbody.innerHTML = currentPass.members
            .map(
              (m, i) => `
              <tr style="border-top: 1px solid #E2E8F0;">
                <td style="padding: 0.4rem 0.6rem; color: var(--text-muted);">${i + 1}</td>
                <td style="padding: 0.4rem 0.6rem; font-weight: 600;">${m.member_name}</td>
                <td style="padding: 0.4rem 0.6rem;">${m.member_age}y</td>
                <td style="padding: 0.4rem 0.6rem; font-family: monospace;">${m.member_mobile || '—'}</td>
              </tr>
            `
            )
            .join('');
        } else {
          tbody.innerHTML = `
            <tr>
              <td colspan="4" style="padding: 0.6rem; text-align: center; color: var(--text-muted); font-style: italic;">
                Solo Visitor (No additional members)
              </td>
            </tr>
          `;
        }
      }
    }

    // Update Dynamic QR Code
    const qrImg = document.querySelector('.pass-qr-box img.qr-image');
    const verifyPath = window.location.href.replace(/pass\.html.*$/, '') + `verify.html?code=${encodeURIComponent(currentPass.reg_code)}`;
    if (qrImg) {
      qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(verifyPath)}`;
    }
    const manualLink = document.querySelector('.pass-qr-box a');
    if (manualLink) {
      manualLink.href = `verify.html?code=${encodeURIComponent(currentPass.reg_code)}`;
    }

    // Update HMAC Signature Footer
    const hmacEl = document.querySelector('.hmac-hash');
    if (hmacEl) {
      hmacEl.textContent = currentPass.hmac_signature;
    }

    // Update SVG Venue Blueprint Route Map
    updateSvgBlueprint(currentPass.gate_id);
  }

  function updateSvgBlueprint(gateId) {
    const svg = document.querySelector('.map-svg-container svg');
    if (!svg) return;

    // Reset all exit gates rects
    const gateMappings = [
      { id: 'exit_1', selector: 'g[transform*="20, 140"]' },
      { id: 'exit_2', selector: 'g[transform*="285, 15"]' },
      { id: 'exit_3', selector: 'g[transform*="550, 140"]' },
      { id: 'exit_4', selector: 'g[transform*="510, 295"]' }
    ];

    gateMappings.forEach(mapping => {
      const g = svg.querySelector(mapping.selector);
      if (!g) return;
      const rect = g.querySelector('rect');
      const texts = g.querySelectorAll('text');
      const isCurrent = mapping.id === gateId;

      if (rect) {
        rect.setAttribute('fill', isCurrent ? '#00ADB5' : '#1E293B');
        rect.setAttribute('stroke', isCurrent ? '#FFFFFF' : '#475569');
        rect.setAttribute('stroke-width', isCurrent ? '3' : '1');
      }
      texts.forEach(t => {
        t.setAttribute('fill', isCurrent ? '#0B192C' : '#CBD5E1');
      });
    });

    // Remove existing highlighted route paths
    const existingRoutes = svg.querySelectorAll('.dynamic-route-path');
    existingRoutes.forEach(r => r.remove());

    // Insert active path
    let pathD = '';
    let endCircle = { cx: 0, cy: 0 };

    if (gateId === 'exit_1') {
      pathD = 'M 350 295 L 350 165 L 150 165';
      endCircle = { cx: 150, cy: 165 };
    } else if (gateId === 'exit_2') {
      pathD = 'M 350 295 L 350 65';
      endCircle = { cx: 350, cy: 65 };
    } else if (gateId === 'exit_3') {
      pathD = 'M 350 295 L 350 165 L 550 165';
      endCircle = { cx: 550, cy: 165 };
    } else if (gateId === 'exit_4') {
      pathD = 'M 350 295 L 350 270 L 510 270 L 510 295';
      endCircle = { cx: 510, cy: 295 };
    }

    if (pathD) {
      const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      pathEl.setAttribute('class', 'dynamic-route-path');
      pathEl.setAttribute('d', pathD);
      pathEl.setAttribute('fill', 'none');
      pathEl.setAttribute('stroke', '#00ADB5');
      pathEl.setAttribute('stroke-width', '4');
      pathEl.setAttribute('stroke-linecap', 'round');
      pathEl.setAttribute('stroke-linejoin', 'round');
      pathEl.setAttribute('filter', 'url(#glow)');

      const circleEl = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circleEl.setAttribute('class', 'dynamic-route-path');
      circleEl.setAttribute('cx', endCircle.cx);
      circleEl.setAttribute('cy', endCircle.cy);
      circleEl.setAttribute('r', '6');
      circleEl.setAttribute('fill', '#FFFFFF');

      svg.appendChild(pathEl);
      svg.appendChild(circleEl);
    }
  }

  // 7. Intercept Admin Login on login.html
  function initAdminLogin() {
    const loginForm = document.querySelector('form[action*="login"]');
    if (!loginForm) return;

    if (isStaticEnvironment()) {
      loginForm.setAttribute('onsubmit', 'return false;');
      loginForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const pwd = document.getElementById('password')?.value;
        if (pwd === 'admin123') {
          sessionStorage.setItem('is_admin', 'true');
          window.location.href = 'admin.html';
        } else {
          alert('Invalid password! Default password is: admin123');
        }
        return false;
      });
    }
  }

  // 8. Hydrate Admin Dashboard on admin.html
  function initAdminDashboard() {
    const adminContainer = document.querySelector('.admin-dashboard-container');
    if (!adminContainer) return;

    const passes = getStoredPasses();
    let totalHeadcount = 0;
    let admittedCount = 0;
    const gateStats = { exit_1: 0, exit_2: 0, exit_3: 0, exit_4: 0 };

    passes.forEach(p => {
      const count = p.group_count || 1;
      totalHeadcount += count;
      if (p.checked_in === 1) admittedCount += count;
      if (gateStats[p.gate_id] !== undefined) gateStats[p.gate_id] += count;
    });

    // Update KPI stat numbers
    const statCards = document.querySelectorAll('.stat-card');
    if (statCards.length >= 3) {
      const num1 = statCards[0].querySelector('.stat-number');
      if (num1) num1.textContent = totalHeadcount;

      const num2 = statCards[1].querySelector('.stat-number');
      if (num2) num2.textContent = passes.length;

      const num3 = statCards[2].querySelector('.stat-number');
      if (num3) num3.textContent = admittedCount;

      const ind3 = statCards[2].querySelector('.stat-indicator');
      if (ind3 && totalHeadcount > 0) {
        const pct = Math.round((admittedCount / totalHeadcount) * 100);
        ind3.textContent = `${pct}% of total visitors entered`;
      }
    }

    // Update Gate Capacity Grid
    const gateBoxes = document.querySelectorAll('.gate-capacity-grid .gate-stat-box');
    const gateOrder = ['exit_1', 'exit_2', 'exit_3', 'exit_4'];
    gateBoxes.forEach((box, i) => {
      const gid = gateOrder[i];
      const count = gateStats[gid] || 0;
      const pct = totalHeadcount > 0 ? Math.round((count / totalHeadcount) * 100) : 0;

      const countSpan = box.querySelector('.gate-theme-color');
      if (countSpan) countSpan.textContent = `${count} pax`;

      const bar = box.querySelector('.progress-bar-fill');
      if (bar) bar.style.width = `${pct}%`;

      const pctText = box.querySelector('.gate-stat-box > div:last-child');
      if (pctText) pctText.textContent = `${pct}% crowd share`;
    });

    // Update Registrations Table
    const tbody = document.querySelector('#registrationsTable tbody');
    if (tbody && isStaticEnvironment()) {
      tbody.innerHTML = passes
        .map(
          (p, idx) => `
        <tr style="border-top: 1px solid #E2E8F0;">
          <td class="mono-font" style="font-weight: 700; color: var(--accent-teal);">
            <a href="pass.html?code=${encodeURIComponent(p.reg_code)}" style="color: inherit; text-decoration: underline;">
              ${p.reg_code}
            </a>
          </td>
          <td style="font-size: 0.82rem; color: var(--text-muted);">${p.created_at || 'Just now'}</td>
          <td style="font-weight: 600;">${p.primary_name} (${p.age || '—'}y)</td>
          <td class="mono-font">${p.mobile}</td>
          <td><span class="badge badge-teal">${p.group_count} pax</span></td>
          <td><span class="badge" style="background: #E2E8F0; color: var(--secondary-navy);">${p.assigned_gate}</span></td>
          <td>
            <span class="badge ${p.checked_in === 1 ? 'badge-success' : 'badge-warning'}">
              ${p.checked_in === 1 ? 'Admitted' : 'Pending Entry'}
            </span>
          </td>
          <td style="text-align: right; white-space: nowrap;">
            <button class="btn btn-outline" style="padding: 0.25rem 0.6rem; font-size: 0.78rem;" onclick="toggleAdminCheckIn('${p.reg_code}')">
              ${p.checked_in === 1 ? '↩️ Undo' : '🚪 Admit'}
            </button>
            <a href="pass.html?code=${encodeURIComponent(p.reg_code)}" class="btn btn-primary" style="padding: 0.25rem 0.6rem; font-size: 0.78rem;">
              View Pass
            </a>
          </td>
        </tr>
      `
        )
        .join('');
    }
  }

  // Admin Check-In helper
  window.toggleAdminCheckIn = function (regCode) {
    const passes = getStoredPasses();
    const p = passes.find(item => item.reg_code === regCode);
    if (p) {
      p.checked_in = p.checked_in === 1 ? 0 : 1;
      p.checked_in_at = p.checked_in === 1 ? new Date().toISOString().replace('T', ' ').substring(0, 19) : null;
      try {
        localStorage.setItem('venue_passes', JSON.stringify(passes));
      } catch (e) {}
      initAdminDashboard();
    }
  };

  // 9. Hydrate Security Guard Terminal on verify.html
  function initVerifyTerminal() {
    const verifyCard = document.querySelector('.terminal-card');
    if (!verifyCard) return;

    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    if (!code) return;

    const passes = getStoredPasses();
    const p = passes.find(item => item.reg_code === code);
    if (!p) return;

    // Update status card
    const statusDesc = document.querySelector('.status-desc');
    if (statusDesc) {
      statusDesc.textContent = `Cryptographic Signature Authenticated for ${p.reg_code}. Authorized for Single Entry Gate.`;
    }

    // Update headcount
    const countBig = document.querySelector('.terminal-body div[style*="font-size: 2.2rem"]');
    if (countBig) countBig.textContent = p.group_count;

    // Update gate
    const gateTitle = document.querySelector('.terminal-body div[style*="font-size: 1.4rem"]');
    if (gateTitle) gateTitle.textContent = p.assigned_gate;

    // Update check-in status
    const statusText = document.getElementById('checkInStatusText');
    const iconSpan = document.getElementById('checkInBtnIcon');
    const btn = document.getElementById('checkInBtn');

    if (statusText) {
      if (p.checked_in === 1) {
        statusText.innerHTML = `<span style="color: #059669; font-weight: 700;">● Admitted into venue at ${p.checked_in_at || 'Terminal'}</span>`;
        if (iconSpan) iconSpan.textContent = '↩️ Undo Admission';
        if (btn) btn.className = 'btn btn-outline btn-admitted';
      } else {
        statusText.innerHTML = `<span style="color: #D97706; font-weight: 700;">⏳ Pending physical entry at gate</span>`;
        if (iconSpan) iconSpan.textContent = '🚪 Mark as Admitted';
        if (btn) btn.className = 'btn btn-primary';
      }
    }

    if (btn && isStaticEnvironment()) {
      btn.onclick = function () {
        p.checked_in = p.checked_in === 1 ? 0 : 1;
        p.checked_in_at = p.checked_in === 1 ? new Date().toISOString().replace('T', ' ').substring(0, 19) : null;
        try {
          localStorage.setItem('venue_passes', JSON.stringify(passes));
        } catch (e) {}
        initVerifyTerminal();
      };
    }

    // Update visitor table
    const detailsTable = document.querySelector('.terminal-body .pass-details-table');
    if (detailsTable) {
      const rows = detailsTable.querySelectorAll('tr');
      rows.forEach(tr => {
        const th = tr.querySelector('th');
        const td = tr.querySelector('td');
        if (!th || !td) return;
        const text = th.textContent.toLowerCase();
        if (text.includes('pass code')) td.textContent = p.reg_code;
        else if (text.includes('primary visitor')) td.textContent = `${p.primary_name} (Age: ${p.age})`;
        else if (text.includes('mobile')) td.textContent = p.mobile;
        else if (text.includes('address')) td.textContent = p.address;
        else if (text.includes('assigned exit')) td.textContent = `${p.assigned_gate} (${p.assigned_group})`;
      });
    }
  }

  // Execute on DOM Ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }

  function onReady() {
    injectStaticBanner();
    initRegistrationForm();
    initPassView();
    initAdminLogin();
    initAdminDashboard();
    initVerifyTerminal();
  }
})();
