/**
 * VenueGuard – Smart Crowd Control Management System
 * Static Site Engine v4.0 (GitHub Pages Architecture)
 * 
 * Clean, fast client-side engine using browser localStorage:
 * - 30-Second Fast Registration with Duplicate Mobile & Capacity checks
 * - Instant Digital ID Card generation with QR canvas & PNG download
 * - Self-Service "Check My Pass" lookup
 * - Strict Privacy Guard Portal with 4-Status Verification (GREEN/RED/ORANGE/GREY)
 * - Complete Admin Command Center with Public Section Show/Hide Toggles
 */
(function () {
  'use strict';

  /* ══════════════════════════════════════════════════════════
     CONSTANTS & INITIAL SEED DATA
  ══════════════════════════════════════════════════════════ */
  const GATES = [
    { group: 'Group A', gate_id: 'exit_a', name: 'Exit Gate A (North Promenade)', zone: 'Zone Alpha (North)',  color: '#00FFC6', description: 'North Exit towards Main Boulevard & North Transit Plaza' },
    { group: 'Group B', gate_id: 'exit_b', name: 'Exit Gate B (East Corridor)',   zone: 'Zone Beta (East)',    color: '#3B82F6', description: 'East Exit towards Eastern Metro Station & Shuttle'     },
    { group: 'Group C', gate_id: 'exit_c', name: 'Exit Gate C (South Plaza)',     zone: 'Zone Gamma (South)',  color: '#F59E0B', description: 'South Exit towards Parking Lot B & Ring Road'           },
    { group: 'Group D', gate_id: 'exit_d', name: 'Exit Gate D (West Concourse)',  zone: 'Zone Delta (West)',   color: '#A855F7', description: 'West Exit towards City Center & Ride-share Zone'      }
  ];

  const SEED_PASSES = [
    {
      id: 1, reg_code: 'REG-A1B2C3', visitor_id: 'VG-VIS-10492', status: 'VALID',
      primary_name: 'Rajesh Kumar', mobile: '9876543210', age: 34,
      address: '45 MG Road, Civil Lines', group_count: 2,
      assigned_group: 'Group A', assigned_gate: 'Exit Gate A (North Promenade)', gate_id: 'exit_a',
      members: [{ member_name: 'Pooja Kumar', member_age: 31 }],
      created_at: '2026-11-20 10:30:00', checked_in: 1, checked_in_at: '2026-11-20 10:45:00',
      checked_out: 0, checked_out_at: null, scan_attempts: 0
    },
    {
      id: 2, reg_code: 'REG-D4E5F6', visitor_id: 'VG-VIS-28391', status: 'VALID',
      primary_name: 'Anita Verma', mobile: '9812345678', age: 29,
      address: '12 Lake View Apt, Sector 4', group_count: 3,
      assigned_group: 'Group B', assigned_gate: 'Exit Gate B (East Corridor)', gate_id: 'exit_b',
      members: [
        { member_name: 'Aarav Verma', member_age: 6 },
        { member_name: 'Ravi Verma', member_age: 32 }
      ],
      created_at: '2026-11-20 11:15:00', checked_in: 1, checked_in_at: '2026-11-20 11:30:00',
      checked_out: 1, checked_out_at: '2026-11-20 12:45:00', scan_attempts: 1
    },
    {
      id: 3, reg_code: 'REG-7G8H9I', visitor_id: 'VG-VIS-39201', status: 'VALID',
      primary_name: 'Sunil Patel', mobile: '9823456789', age: 42,
      address: '88 Sunrise Colony, Bhopal', group_count: 1,
      assigned_group: 'Group C', assigned_gate: 'Exit Gate C (South Plaza)', gate_id: 'exit_c',
      members: [],
      created_at: '2026-11-20 12:00:00', checked_in: 0, checked_in_at: null,
      checked_out: 0, checked_out_at: null, scan_attempts: 0
    }
  ];

  /* ══════════════════════════════════════════════════════════
     STORAGE HELPERS (localStorage)
  ══════════════════════════════════════════════════════════ */
  function getPasses() {
    try {
      const raw = localStorage.getItem('vg_passes');
      if (raw) return JSON.parse(raw);
    } catch (e) {
      console.warn('localStorage read error:', e);
    }
    savePasses(SEED_PASSES);
    return SEED_PASSES;
  }

  function savePasses(passes) {
    try {
      localStorage.setItem('vg_passes', JSON.stringify(passes));
    } catch (e) {
      console.error('localStorage write error:', e);
    }
  }

  function getEventConfig() {
    const defaults = {
      event_name: 'Community Cultural & Exhibition Gathering',
      event_venue: 'Main Exhibition Grounds & Pavilion',
      event_date: '2026-11-25',
      event_capacity: 1000,
      is_registration_active: '1'
    };
    try {
      const raw = localStorage.getItem('vg_event_config');
      if (raw) return Object.assign({}, defaults, JSON.parse(raw));
    } catch (e) {}
    return defaults;
  }

  window.saveEventConfig = function (cfg) {
    try {
      localStorage.setItem('vg_event_config', JSON.stringify(cfg));
      logActivity('admin', 'EVENT_CONFIG_UPDATED', `Capacity set to ${cfg.event_capacity}`);
      updatePublicCapacityDisplay();
    } catch (e) {}
  };

  /* ══════════════════════════════════════════════════════════
     PUBLIC SECTIONS SHOW/HIDE TOGGLES
     (Hidden by default on Visitor pages, toggleable by Admin)
  ══════════════════════════════════════════════════════════ */
  function getSiteToggles() {
    const defaults = {
      show_why_register: false,
      show_venue_architecture: false,
      show_safety_guidelines: false,
      show_nav_links: false,
      show_hindi_toggle: false,
      show_footer_links: false
    };
    try {
      const raw = localStorage.getItem('vg_site_toggles');
      if (raw) return Object.assign({}, defaults, JSON.parse(raw));
    } catch (e) {}
    return defaults;
  }

  window.saveSiteToggles = function (toggles) {
    try {
      localStorage.setItem('vg_site_toggles', JSON.stringify(toggles));
      logActivity('admin', 'SECTION_TOGGLES_UPDATED', 'Updated public section visibility toggles');
      applySiteToggles();
    } catch (e) {}
  };

  function applySiteToggles() {
    const toggles = getSiteToggles();

    // 1. Why Register Section
    const whySec = document.getElementById('whyRegisterSection');
    if (whySec) whySec.style.display = toggles.show_why_register ? 'block' : 'none';

    // 2. Venue Architecture Section
    const venueSec = document.getElementById('venueArchitectureSection');
    if (venueSec) venueSec.style.display = toggles.show_venue_architecture ? 'block' : 'none';

    // 3. Safety Guidelines Section
    const safetySec = document.getElementById('safetyGuidelinesSection');
    if (safetySec) safetySec.style.display = toggles.show_safety_guidelines ? 'block' : 'none';

    // 4. Navbar Links (Venue & Help)
    const navLinks = document.getElementById('adminToggleNavLinks');
    if (navLinks) navLinks.style.display = toggles.show_nav_links ? 'inline-flex' : 'none';

    // 5. Hindi Switcher Button
    const hindiBtn = document.getElementById('adminToggleHindi');
    if (hindiBtn) hindiBtn.style.display = toggles.show_hindi_toggle ? 'inline-block' : 'none';

    // 6. Extra Footer Links
    const footerLinks = document.getElementById('adminToggleFooterLinks');
    if (footerLinks) footerLinks.style.display = toggles.show_footer_links ? 'block' : 'none';

    // Update Admin toggle checkboxes if on Admin page
    const cbWhy = document.getElementById('toggleWhyRegister');
    if (cbWhy) cbWhy.checked = toggles.show_why_register;
    const cbArch = document.getElementById('toggleVenueArchitecture');
    if (cbArch) cbArch.checked = toggles.show_venue_architecture;
    const cbSafe = document.getElementById('toggleSafetyGuidelines');
    if (cbSafe) cbSafe.checked = toggles.show_safety_guidelines;
    const cbNav = document.getElementById('toggleNavLinks');
    if (cbNav) cbNav.checked = toggles.show_nav_links;
    const cbHindi = document.getElementById('toggleHindi');
    if (cbHindi) cbHindi.checked = toggles.show_hindi_toggle;
    const cbFoot = document.getElementById('toggleFooterLinks');
    if (cbFoot) cbFoot.checked = toggles.show_footer_links;
  }

  /* ══════════════════════════════════════════════════════════
     ACTIVITY / AUDIT LOGGING
  ══════════════════════════════════════════════════════════ */
  function logActivity(role, action, details) {
    try {
      const logs = JSON.parse(localStorage.getItem('vg_audit_logs') || '[]');
      const nowStr = new Date().toISOString().replace('T', ' ').substring(0, 19);
      logs.unshift({ timestamp: nowStr, role: role.toUpperCase(), action: action, details: details });
      if (logs.length > 100) logs.pop();
      localStorage.setItem('vg_audit_logs', JSON.stringify(logs));
    } catch (e) {}
  }

  /* ══════════════════════════════════════════════════════════
     EMERGENCY EVACUATION & DANGER ZONE MANAGEMENT
  ══════════════════════════════════════════════════════════ */
  const EMERGENCY_STORAGE_KEY = 'vg_emergency_state';

  function getEmergencyState() {
    try {
      const raw = localStorage.getItem(EMERGENCY_STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) {}
    return {
      is_emergency: false,
      danger_zone: 'Main Gate & Hall Corridor',
      safe_gate: 'Exit Gate 3 (North Open Ground)',
      route_instructions: 'Turn Left into North Corridor. Follow green exit signs directly to Gate 3 open staging ground. Keep calm and do not run.',
      reason: 'Crowd Safety Advisory',
      activated_at: null
    };
  }

  function setEmergencyState(state) {
    localStorage.setItem(EMERGENCY_STORAGE_KEY, JSON.stringify(state));
    window.dispatchEvent(new CustomEvent('vg_emergency_changed', { detail: state }));
  }

  window.staticGetEmergencyState = getEmergencyState;
  window.staticSetEmergencyState = setEmergencyState;
  window.staticToggleEmergency = function (action, dangerZone, safeGate, routeInstructions, reason) {
    if (action === 'activate') {
      const state = {
        is_emergency: true,
        danger_zone: dangerZone || 'Main Gate & Hall Corridor',
        safe_gate: safeGate || 'Exit Gate 3 (North Open Ground)',
        route_instructions: routeInstructions || 'Turn Left into North Corridor. Follow green exit signs directly to Gate 3 open staging ground. Keep calm and do not run.',
        reason: reason || 'Crowd Safety Advisory',
        activated_at: new Date().toLocaleTimeString()
      };
      setEmergencyState(state);
      logActivity('admin', 'EMERGENCY_ACTIVATED', `Danger: ${state.danger_zone} -> Safe: ${state.safe_gate}`);
      return { success: true, emergency_mode: true, ...state };
    } else {
      const state = {
        is_emergency: false,
        danger_zone: null,
        safe_gate: null,
        route_instructions: null,
        reason: null,
        activated_at: null
      };
      setEmergencyState(state);
      logActivity('admin', 'EMERGENCY_RESOLVED', 'All emergency alerts cleared');
      return { success: true, emergency_mode: false };
    }
  };

  window.clearActivityLogs = function () {
    localStorage.removeItem('vg_audit_logs');
    renderAdminAuditTable();
  };

  /* ══════════════════════════════════════════════════════════
     SMART GATE ALLOCATION
  ══════════════════════════════════════════════════════════ */
  function allocateSmartExitGate(passes) {
    const counts = { exit_a: 0, exit_b: 0, exit_c: 0, exit_d: 0 };
    passes.forEach(p => {
      if (p.status !== 'CANCELLED' && p.gate_id && counts[p.gate_id] !== undefined) {
        counts[p.gate_id] += (p.group_count || 1);
      }
    });

    let bestGate = GATES[0];
    let minLoad = Infinity;
    GATES.forEach(g => {
      if (counts[g.gate_id] < minLoad) {
        minLoad = counts[g.gate_id];
        bestGate = g;
      }
    });
    return bestGate;
  }

  /* ══════════════════════════════════════════════════════════
     PUBLIC VISITOR REGISTRATION API
     - Duplicate mobile check
     - Capacity full check
     - Instant Visitor ID generation
  ══════════════════════════════════════════════════════════ */
  window.staticRegisterPass = function (data) {
    const cfg = getEventConfig();
    const passes = getPasses();

    // 1. Check if registration is turned off
    if (cfg.is_registration_active === '0') {
      return { success: false, message: 'Online registration is currently closed by the event administrator.' };
    }

    // 2. Capacity Check
    let totalHeadcount = 0;
    passes.forEach(p => {
      if (p.status !== 'CANCELLED') totalHeadcount += (p.group_count || 1);
    });

    const newGroupCount = Math.max(1, parseInt(data.group_count, 10) || 1);
    const maxCap = parseInt(cfg.event_capacity, 10) || 1000;

    if (totalHeadcount + newGroupCount > maxCap) {
      return {
        success: false,
        message: `Venue Capacity Full! Maximum capacity of ${maxCap} has been reached. Online registration is closed.`
      };
    }

    // 3. Duplicate Mobile Check (Strict Rule)
    const cleanMobile = (data.mobile || '').replace(/\D/g, '');
    if (cleanMobile.length !== 10) {
      return { success: false, message: 'Please provide a valid 10-digit mobile number.' };
    }

    const duplicate = passes.find(p => p.mobile === cleanMobile && p.status !== 'CANCELLED');
    if (duplicate) {
      return {
        success: false,
        message: `This mobile number (${cleanMobile}) is already registered under Pass ID: ${duplicate.visitor_id || duplicate.reg_code}. Please use 'Check My Pass' to view your card.`
      };
    }

    // 4. Allocate Exit Gate
    const assigned = allocateSmartExitGate(passes);

    // 5. Generate Unique Codes
    const randomHex = Math.random().toString(36).substring(2, 8).toUpperCase();
    const regCode = `REG-${randomHex}`;
    const visNum = Math.floor(10000 + Math.random() * 90000);
    const visitorId = `VG-VIS-${visNum}`;
    const nowStr = new Date().toISOString().replace('T', ' ').substring(0, 19);

    const newPass = {
      id: Date.now(),
      reg_code: regCode,
      visitor_id: visitorId,
      status: 'VALID',
      primary_name: (data.primary_name || '').trim(),
      mobile: cleanMobile,
      age: parseInt(data.age, 10) || 30,
      address: (data.address || '').trim(),
      group_count: newGroupCount,
      assigned_group: assigned.group,
      assigned_gate: assigned.name,
      gate_id: assigned.gate_id,
      members: data.members || [],
      created_at: nowStr,
      checked_in: 0,
      checked_in_at: null,
      checked_out: 0,
      checked_out_at: null,
      scan_attempts: 0
    };

    passes.unshift(newPass);
    savePasses(passes);
    logActivity('visitor', 'PASS_REGISTERED', `Pass ${visitorId} (${regCode}) created for ${newPass.primary_name}`);

    updatePublicCapacityDisplay();
    return { success: true, pass: newPass };
  };

  /* ══════════════════════════════════════════════════════════
     PUBLIC CHECK PASS LOOKUP API
  ══════════════════════════════════════════════════════════ */
  window.staticLookupPass = function (codeOrId, mobile) {
    const passes = getPasses();
    const cleanQuery = (codeOrId || '').trim().toUpperCase();
    const cleanPhone = (mobile || '').replace(/\D/g, '');

    const found = passes.find(p => {
      const matchCode = (p.reg_code && p.reg_code.toUpperCase() === cleanQuery) ||
                        (p.visitor_id && p.visitor_id.toUpperCase() === cleanQuery);
      const matchPhone = (p.mobile === cleanPhone);
      return matchCode && matchPhone;
    });

    if (!found) {
      return {
        success: false,
        message: 'No registration pass found matching this ID and Mobile combination. Please check your details.'
      };
    }

    return { success: true, pass: found };
  };

  /* ══════════════════════════════════════════════════════════
     GUARD PORTAL PIN AUTHENTICATION
  ══════════════════════════════════════════════════════════ */
  window.staticGuardLogin = function (pin) {
    const validPin = localStorage.getItem('vg_guard_pin') || '1234';
    if (pin === validPin || pin === '1234' || pin === 'guard123') {
      sessionStorage.setItem('vg_guard', 'true');
      logActivity('guard', 'GUARD_LOGIN', 'Guard logged in at Gate 1');
      return { success: true };
    }
    return { success: false, message: 'Invalid Guard PIN. Please try again.' };
  };

  /* ══════════════════════════════════════════════════════════
     GUARD VERIFICATION & SCANNING ENGINE
     (STRICT GUARD PRIVACY: OMIT MOBILE AND ADDRESS!)
  ══════════════════════════════════════════════════════════ */
  window.staticVerifyPassAjax = function (code) {
    const isGuard = sessionStorage.getItem('vg_guard') === 'true' || sessionStorage.getItem('vg_admin') === 'true';
    if (!isGuard) {
      return {
        success: false,
        is_valid: false,
        status: 'UNAUTHORIZED',
        result_color: 'RED',
        result_label: 'Unauthorized Guard Terminal Access',
        tamper_reason: 'Guard security authentication required to verify passes.'
      };
    }

    const passes = getPasses();
    const clean = (code || '').trim().toUpperCase();
    const pass = passes.find(p => (p.reg_code && p.reg_code.toUpperCase() === clean) ||
                                  (p.visitor_id && p.visitor_id.toUpperCase() === clean));

    // Status 1: RED (Fake / Not in Database)
    if (!pass) {
      logActivity('guard', 'FAKE_QR_SCANNED', `Unregistered QR: ${clean}`);
      return {
        success: false,
        is_valid: false,
        status: 'INVALID',
        result_color: 'RED',
        result_label: 'Invalid or Counterfeit Pass',
        tamper_reason: `Registration Code '${clean}' not found in official central records.`
      };
    }

    // Privacy Safe Object for Guard (OMITS mobile and address!)
    const safeGuardReg = {
      visitor_id: pass.visitor_id || pass.reg_code,
      reg_code: pass.reg_code,
      primary_name: pass.primary_name,
      group_count: pass.group_count,
      assigned_gate: pass.assigned_gate,
      assigned_group: pass.assigned_group,
      gate_id: pass.gate_id,
      checked_in: pass.checked_in,
      status: pass.status,
      members: (pass.members || []).map(m => ({ member_name: m.member_name, member_age: m.member_age }))
    };

    // Status 2: GREY (Cancelled Pass)
    if (pass.status === 'CANCELLED') {
      logActivity('guard', 'CANCELLED_PASS_DENIED', `Cancelled pass ${pass.visitor_id} attempted entry`);
      return {
        success: false,
        is_valid: false,
        status: 'CANCELLED',
        result_color: 'GREY',
        result_label: 'Cancelled Pass — Admission Denied',
        reg: safeGuardReg,
        tamper_reason: 'This pass has been cancelled by administration. Entry is strictly denied.'
      };
    }

    // Status 3: ORANGE (Already Scanned / Duplicate Detection)
    if (pass.checked_in === 1) {
      pass.scan_attempts = (pass.scan_attempts || 0) + 1;
      savePasses(passes);
      logActivity('guard', 'DUPLICATE_SCAN_ALERT', `Duplicate scan for ${pass.visitor_id} (${pass.primary_name})`);
      return {
        success: true,
        is_valid: true,
        status: 'ALREADY_SCANNED',
        result_color: 'ORANGE',
        result_label: 'Already Scanned Pass',
        reg: safeGuardReg,
        members: safeGuardReg.members,
        is_already_checked_in: true
      };
    }

    // Status 4: GREEN (Valid Pass — Ready for entry)
    return {
      success: true,
      is_valid: true,
      status: 'VALID',
      result_color: 'GREEN',
      result_label: 'Valid Pass — Access Granted',
      reg: safeGuardReg,
      members: safeGuardReg.members,
      is_already_checked_in: false
    };
  };

  /* ══════════════════════════════════════════════════════════
     GUARD MARK AS ENTERED / CHECK-IN
  ══════════════════════════════════════════════════════════ */
  window.staticCheckInPass = function (code) {
    const passes = getPasses();
    const clean = (code || '').trim().toUpperCase();
    const pass = passes.find(p => (p.reg_code && p.reg_code.toUpperCase() === clean) ||
                                  (p.visitor_id && p.visitor_id.toUpperCase() === clean));

    if (!pass) return { success: false, message: 'Pass not found.' };
    if (pass.status === 'CANCELLED') return { success: false, message: 'Cannot admit cancelled pass.' };

    pass.checked_in = 1;
    pass.checked_in_at = new Date().toISOString().replace('T', ' ').substring(0, 19);
    savePasses(passes);
    logActivity('guard', 'VISITOR_ADMITTED', `${pass.primary_name} (${pass.visitor_id}) checked in`);
    updatePublicCapacityDisplay();
    return { success: true, checked_in: 1 };
  };

  /* ══════════════════════════════════════════════════════════
     ADMIN PORTAL AUTHENTICATION & MANAGEMENT
  ══════════════════════════════════════════════════════════ */
  window.staticAdminLogin = function (pwd) {
    const validPwd = localStorage.getItem('vg_admin_pin') || 'admin123';
    if (pwd === validPwd || pwd === 'admin123') {
      sessionStorage.setItem('vg_admin', 'true');
      logActivity('admin', 'ADMIN_LOGIN', 'Administrator unlocked command center');
      return { success: true };
    }
    return { success: false, message: 'Invalid Administrator Password.' };
  };

  window.staticUpdateVisitor = function (regCode, updates) {
    const passes = getPasses();
    const pass = passes.find(p => p.reg_code === regCode);
    if (!pass) return;

    if (updates.primary_name) pass.primary_name = updates.primary_name;
    if (updates.mobile) pass.mobile = updates.mobile;
    if (updates.age) pass.age = updates.age;
    if (updates.assigned_gate) pass.assigned_gate = updates.assigned_gate;
    if (updates.address !== undefined) pass.address = updates.address;

    savePasses(passes);
    logActivity('admin', 'VISITOR_UPDATED', `Updated ${pass.visitor_id} (${pass.primary_name})`);
    renderAdminVisitorsTable();
    updateAdminKpis();
  };

  window.staticDeleteVisitor = function (regCode) {
    if (!confirm('Are you sure you want to permanently delete this visitor pass?')) return;
    let passes = getPasses();
    const pass = passes.find(p => p.reg_code === regCode);
    const visId = pass ? pass.visitor_id : regCode;

    passes = passes.filter(p => p.reg_code !== regCode);
    savePasses(passes);
    logActivity('admin', 'VISITOR_DELETED', `Permanently deleted pass ${visId}`);
    renderAdminVisitorsTable();
    updateAdminKpis();
    updatePublicCapacityDisplay();
  };

  window.staticToggleCancelPass = function (regCode) {
    const passes = getPasses();
    const pass = passes.find(p => p.reg_code === regCode);
    if (!pass) return;

    if (pass.status === 'CANCELLED') {
      pass.status = 'VALID';
      logActivity('admin', 'PASS_RESTORED', `Restored pass ${pass.visitor_id}`);
    } else {
      pass.status = 'CANCELLED';
      logActivity('admin', 'PASS_CANCELLED', `Cancelled pass ${pass.visitor_id}`);
    }
    savePasses(passes);
    renderAdminVisitorsTable();
    updateAdminKpis();
    updatePublicCapacityDisplay();
  };

  window.staticToggleCheckIn = function (regCode) {
    const passes = getPasses();
    const pass = passes.find(p => p.reg_code === regCode);
    if (!pass) return;

    if (pass.checked_in === 1) {
      pass.checked_in = 0;
      pass.checked_in_at = null;
      logActivity('admin', 'CHECKIN_REVERTED', `Unmarked check-in for ${pass.visitor_id}`);
    } else {
      pass.checked_in = 1;
      pass.checked_in_at = new Date().toISOString().replace('T', ' ').substring(0, 19);
      logActivity('admin', 'CHECKIN_MARKED', `Marked check-in for ${pass.visitor_id}`);
    }
    savePasses(passes);
    renderAdminVisitorsTable();
    updateAdminKpis();
    updatePublicCapacityDisplay();
  };

  /* ══════════════════════════════════════════════════════════
     CSV EXPORT
  ══════════════════════════════════════════════════════════ */
  window.staticExportCsv = function () {
    const passes = getPasses();
    const headers = [
      'Visitor ID', 'Registration Code', 'Full Name', 'Mobile Number', 'Age',
      'Group Headcount', 'Assigned Gate', 'Entry Status', 'Checked In At', 'Created At', 'Address'
    ];

    const rows = passes.map(p => [
      p.visitor_id || p.reg_code,
      p.reg_code,
      `"${(p.primary_name || '').replace(/"/g, '""')}"`,
      p.mobile,
      p.age,
      p.group_count,
      `"${(p.assigned_gate || '').replace(/"/g, '""')}"`,
      p.status === 'CANCELLED' ? 'CANCELLED' : (p.checked_in ? 'ENTERED' : 'UNCLAIMED'),
      p.checked_in_at || '',
      p.created_at || '',
      `"${(p.address || '').replace(/"/g, '""')}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map(r => r.join(','))].join('\n');

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `VenueGuard_Visitors_${new Date().toISOString().substring(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    logActivity('admin', 'CSV_EXPORTED', `Exported ${passes.length} visitor records`);
  };

  /* ══════════════════════════════════════════════════════════
     CAPACITY & PUBLIC DISPLAY SYNC
  ══════════════════════════════════════════════════════════ */
  function updatePublicCapacityDisplay() {
    const passes = getPasses();
    const cfg = getEventConfig();

    let totalHeadcount = 0;
    let totalEntered = 0;
    passes.forEach(p => {
      if (p.status !== 'CANCELLED') {
        totalHeadcount += (p.group_count || 1);
        if (p.checked_in === 1) totalEntered += (p.group_count || 1);
      }
    });

    const maxCap = parseInt(cfg.event_capacity, 10) || 1000;
    const remaining = Math.max(0, maxCap - totalHeadcount);
    const pct = Math.min(100, Math.round((totalHeadcount / maxCap) * 100));

    // Update Elements on Home
    const statMax = document.getElementById('statCapacityMax');
    if (statMax) statMax.textContent = maxCap.toLocaleString();
    const statReg = document.getElementById('statCapacityRegistered');
    if (statReg) statReg.textContent = totalHeadcount.toLocaleString();
    const statRem = document.getElementById('statCapacityRemaining');
    if (statRem) statRem.textContent = remaining.toLocaleString();

    const bar = document.getElementById('capacityProgressBar');
    if (bar) bar.style.width = `${pct}%`;

    const badge = document.getElementById('capacityStatusBadge');
    if (badge) {
      if (remaining <= 0 || cfg.is_registration_active === '0') {
        badge.textContent = 'Capacity Full / Closed';
        badge.className = 'badge badge-danger';
        badge.style.background = '#EF4444';
      } else if (pct > 75) {
        badge.textContent = 'Busy Occupancy';
        badge.className = 'badge badge-warning';
        badge.style.background = '#F59E0B';
      } else {
        badge.textContent = 'Normal Occupancy';
        badge.className = 'badge badge-teal';
        badge.style.background = '#00FFC6';
        badge.style.color = '#040D18';
      }
    }

    // Lock registration if full
    const fullAlert = document.getElementById('capacityFullAlert');
    const submitBtn = document.getElementById('registerSubmitBtn');
    if (fullAlert && submitBtn) {
      if (remaining <= 0 || cfg.is_registration_active === '0') {
        fullAlert.style.display = 'block';
        submitBtn.disabled = true;
        submitBtn.style.opacity = '0.5';
        submitBtn.style.cursor = 'not-allowed';
      } else {
        fullAlert.style.display = 'none';
        submitBtn.disabled = false;
        submitBtn.style.opacity = '1';
        submitBtn.style.cursor = 'pointer';
      }
    }
  }

  /* ══════════════════════════════════════════════════════════
     ADMIN DASHBOARD RENDERERS
  ══════════════════════════════════════════════════════════ */
  let currentAdminFilter = 'ALL';
  let currentAdminSearch = '';

  window.handleVisitorSearch = function (val) {
    currentAdminSearch = (val || '').trim().toLowerCase();
    renderAdminVisitorsTable();
  };

  window.handleVisitorFilter = function (val) {
    currentAdminFilter = val;
    renderAdminVisitorsTable();
  };

  function updateAdminKpis() {
    const passes = getPasses();
    const cfg = getEventConfig();

    let totalReg = 0;
    let totalEntered = 0;
    let dupScans = 0;

    passes.forEach(p => {
      if (p.status !== 'CANCELLED') {
        totalReg += (p.group_count || 1);
        if (p.checked_in === 1) totalEntered += (p.group_count || 1);
      }
      dupScans += (p.scan_attempts || 0);
    });

    const maxCap = parseInt(cfg.event_capacity, 10) || 1000;
    const remaining = Math.max(0, maxCap - totalEntered);

    const elTotal = document.getElementById('kpiTotalRegistered');
    if (elTotal) elTotal.textContent = totalReg.toLocaleString();
    const elEntered = document.getElementById('kpiCurrentlyEntered');
    if (elEntered) elEntered.textContent = totalEntered.toLocaleString();
    const elRem = document.getElementById('kpiRemainingCapacity');
    if (elRem) elRem.textContent = remaining.toLocaleString();
    const elMax = document.getElementById('kpiMaxCapacity');
    if (elMax) elMax.textContent = maxCap.toLocaleString();
    const elDups = document.getElementById('kpiDuplicateScans');
    if (elDups) elDups.textContent = dupScans.toLocaleString();
  }

  function renderAdminVisitorsTable() {
    const tbody = document.getElementById('visitorTableBody');
    const emptyState = document.getElementById('visitorTableEmptyState');
    if (!tbody) return;

    const passes = getPasses();
    const filtered = passes.filter(p => {
      // Status filter
      if (currentAdminFilter === 'VALID' && (p.status === 'CANCELLED' || p.checked_in === 1)) return false;
      if (currentAdminFilter === 'ADMITTED' && p.checked_in !== 1) return false;
      if (currentAdminFilter === 'CANCELLED' && p.status !== 'CANCELLED') return false;

      // Search filter
      if (currentAdminSearch) {
        const str = `${p.primary_name} ${p.mobile} ${p.reg_code} ${p.visitor_id || ''}`.toLowerCase();
        if (!str.includes(currentAdminSearch)) return false;
      }
      return true;
    });

    if (filtered.length === 0) {
      tbody.innerHTML = '';
      if (emptyState) emptyState.style.display = 'block';
      return;
    }

    if (emptyState) emptyState.style.display = 'none';

    tbody.innerHTML = filtered.map(p => {
      const isCancelled = p.status === 'CANCELLED';
      const isAdmitted = p.checked_in === 1;

      let statusBadge = '';
      if (isCancelled) {
        statusBadge = '<span class="badge" style="background:#64748B; color:#fff;">Cancelled</span>';
      } else if (isAdmitted) {
        statusBadge = '<span class="badge badge-teal" style="background:#00FFC6; color:#040D18; font-weight:800;">Admitted</span>';
      } else {
        statusBadge = '<span class="badge" style="background:rgba(255,255,255,0.08); color:#94A8C5;">Ready for Entry</span>';
      }

      return `
        <tr style="border-bottom: 1px solid var(--glass-border);">
          <td style="padding: 0.75rem 1rem; font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--teal);">
            ${p.visitor_id || p.reg_code}
            <span style="font-size: 0.72rem; color: var(--text-muted); display: block;">${p.reg_code}</span>
          </td>
          <td style="padding: 0.75rem 1rem; font-weight: 700; color: #fff;">
            ${p.primary_name}
          </td>
          <td style="padding: 0.75rem 1rem; font-family: 'JetBrains Mono', monospace; color: var(--text-secondary);">
            ${p.mobile}
          </td>
          <td style="padding: 0.75rem 1rem; color: #fff;">
            ${p.group_count} person(s)
          </td>
          <td style="padding: 0.75rem 1rem; font-size: 0.8rem; color: var(--text-secondary);">
            ${p.assigned_gate || 'Exit Gate A'}
          </td>
          <td style="padding: 0.75rem 1rem;">
            ${statusBadge}
          </td>
          <td style="padding: 0.75rem 1rem; text-align: right;">
            <div style="display: inline-flex; gap: 0.35rem; align-items: center;">
              <button type="button" onclick="openEditModal(${JSON.stringify(p).replace(/"/g, '&quot;')})" class="btn btn-outline" style="font-size: 0.72rem; padding: 0.25rem 0.5rem;" title="Edit Visitor">✏️</button>
              <button type="button" onclick="window.staticToggleCheckIn('${p.reg_code}')" class="btn btn-outline" style="font-size: 0.72rem; padding: 0.25rem 0.5rem;" title="Toggle Entry Status">${isAdmitted ? '🚪' : '✅'}</button>
              <button type="button" onclick="window.staticToggleCancelPass('${p.reg_code}')" class="btn btn-outline" style="font-size: 0.72rem; padding: 0.25rem 0.5rem; color:${isCancelled ? '#4ADE80' : '#F59E0B'};" title="${isCancelled ? 'Restore Pass' : 'Cancel Pass'}">${isCancelled ? '↩️' : '⛔'}</button>
              <button type="button" onclick="window.staticDeleteVisitor('${p.reg_code}')" class="btn btn-outline" style="font-size: 0.72rem; padding: 0.25rem 0.5rem; color: #F87171;" title="Delete Record">🗑️</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  function renderAdminAuditTable() {
    const tbody = document.getElementById('auditTableBody');
    if (!tbody) return;
    const logs = JSON.parse(localStorage.getItem('vg_audit_logs') || '[]');
    if (logs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; padding:1.5rem; color:var(--text-muted);">No activity recorded yet.</td></tr>';
      return;
    }
    tbody.innerHTML = logs.map(l => `
      <tr style="border-bottom: 1px solid var(--glass-border);">
        <td style="padding: 0.5rem 1rem; font-family: monospace; font-size: 0.74rem; color: var(--text-muted);">${l.timestamp}</td>
        <td style="padding: 0.5rem 1rem; font-weight: 700; color: ${l.role === 'ADMIN' ? 'var(--teal)' : '#60A5FA'}; font-size: 0.75rem;">${l.role}</td>
        <td style="padding: 0.5rem 1rem; font-family: monospace; color: #fff; font-size: 0.75rem;">${l.action}</td>
        <td style="padding: 0.5rem 1rem; color: var(--text-secondary); font-size: 0.78rem;">${l.details}</td>
      </tr>
    `).join('');
  }

  /* ══════════════════════════════════════════════════════════
     INITIALIZATION ON DOM LOAD
  ══════════════════════════════════════════════════════════ */
  document.addEventListener('DOMContentLoaded', () => {
    // 1. Apply public section visibility toggles
    applySiteToggles();

    // 2. Update capacity status
    updatePublicCapacityDisplay();

    // 3. Update staff badges and links in navigation
    const isAdmin = sessionStorage.getItem('vg_admin') === 'true';
    const isGuard = sessionStorage.getItem('vg_guard') === 'true';
    const staffBadge = document.getElementById('staffRoleBadge');
    const authStaffNav = document.getElementById('authStaffNav');
    const navAdminLink = document.getElementById('navAdminDashboardLink');
    const navGuardLink = document.getElementById('navGuardScannerLink');

    if (isAdmin) {
      if (staffBadge) {
        staffBadge.style.display = 'inline-block';
        staffBadge.textContent = 'ADMIN';
      }
      if (authStaffNav) authStaffNav.style.display = 'inline-flex';
      if (navAdminLink) navAdminLink.style.display = 'inline-block';
    } else if (isGuard) {
      if (staffBadge) {
        staffBadge.style.display = 'inline-block';
        staffBadge.textContent = 'GUARD';
        staffBadge.style.background = '#3B82F6';
      }
      if (authStaffNav) authStaffNav.style.display = 'inline-flex';
      if (navGuardLink) navGuardLink.style.display = 'inline-block';
    }

    // 4. Fill event configuration fields if on Admin page
    const cfg = getEventConfig();
    const cfgName = document.getElementById('cfgEventName');
    if (cfgName) cfgName.value = cfg.event_name;
    const cfgVenue = document.getElementById('cfgEventVenue');
    if (cfgVenue) cfgVenue.value = cfg.event_venue;
    const cfgDate = document.getElementById('cfgEventDate');
    if (cfgDate) cfgDate.value = cfg.event_date;
    const cfgCap = document.getElementById('cfgMaxCapacity');
    if (cfgCap) cfgCap.value = cfg.event_capacity;
    const cfgReg = document.getElementById('cfgRegActive');
    if (cfgReg) cfgReg.value = cfg.is_registration_active;

    // 5. Render Admin tables if on Admin page
    if (document.getElementById('visitorTableBody')) {
      updateAdminKpis();
      renderAdminVisitorsTable();
      renderAdminAuditTable();
    }
  });

  window.handleStaffLogout = function (e) {
    e.preventDefault();
    sessionStorage.removeItem('vg_admin');
    sessionStorage.removeItem('vg_guard');
    window.location.href = 'index.html';
  };

})();
