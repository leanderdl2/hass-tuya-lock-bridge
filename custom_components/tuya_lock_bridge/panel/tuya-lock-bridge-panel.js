/* Tuya Lock Bridge - sidebar panel.
 *
 * A plain custom element, no framework. Home Assistant hands it a `hass`
 * object with the connection, the states and the user's language; everything
 * here goes through hass.callWS / hass.callService, so the panel shares Home
 * Assistant's own authentication and needs no port, token or API of its own.
 */

const TEXT = {
  en: {
    title: "Locks",
    heading: "Access codes",
    lock: "Lock",
    openDoor: "Open the door",
    codesHeading: "Codes on this lock",
    colName: "Name", colFrom: "Valid from", colUntil: "Valid until", colStatus: "Status",
    loading: "Loading…",
    newHeading: "New code",
    name: "Name", namePlaceholder: "Cleaner", pin: "PIN",
    validFrom: "Valid from", validUntil: "Valid until",
    pattern: "Pattern",
    patContinuous: "Valid throughout that period",
    patDaily: "A fixed window every day",
    patDays: "Only on chosen weekdays",
    patOnce: "Single use - expires once used",
    days: "Days", dayFrom: "Every day from", dayUntil: "Every day until",
    create: "Create code",
    weekdays: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    everyDay: "every day", singleUse: "single use",
    noCodes: "No codes on this lock.",
    remove: "Remove", revoke: "Revoke",
    confirmRemove: 'Remove the record of "{name}" from the list?',
    confirmRevoke: 'Revoke code "{name}"? It will stop working.',
    removedOk: "Record removed.", revokedOk: "Code revoked.",
    failed: "Failed: {err}",
    confirmOpen: 'Open the door of "{name}" now?',
    openedOk: "Door opened.",
    pinDigits: "Enter a PIN of digits only.",
    needTimes: "Enter a start and end time.",
    needDay: "Pick at least one weekday.",
    needWindow: "Fill in the daily time window.",
    createdOk: "Code created. It takes a minute or two before the lock knows it.",
    noLocks: "No locks configured yet. Add the integration under Settings → Devices & services.",
    revoked: "revoked", expired: "expired", scheduled: "scheduled", active: "active",
    unconfirmed: "The lock has not confirmed receiving this code. On WiFi keypads that is normal and the code works anyway.",
    profilesHeading: "Profiles",
    colProfile: "Profile", colMethods: "Unlock methods",
    appAccount: "app account", disabled: "disabled",
    types: { password: "PIN", card: "card", fingerprint: "fingerprint", face: "face" },
    addPin: "+ PIN", addCard: "+ card", rename: "rename",
    promptPin: "PIN for {name}:",
    promptMethodName: 'Name for this method (leave empty for "{name}"):',
    promptRename: "New name for {name}:",
    pinAdded: "PIN added. It works once the lock has picked it up.",
    cardEnrolStarted: "The lock is waiting for a card: hold it against the keypad now. It appears under {name} at the next refresh.",
    methodRenamed: "Renamed.", methodRemoved: "Unlock method removed.",
    confirmRemoveMethod: 'Remove {type} "{name}" from {who}?',
    disable: "Disable", enable: "Enable",
    profileDisabled: "Profile disabled - its codes and cards no longer open the door.",
    profileEnabled: "Profile enabled.",
    deleteProfile: "Delete profile",
    confirmDeleteProfile: 'Delete profile "{name}" and its unlock methods? Cards can only be re-added at the device.',
    profileDeleted: "Profile deleted.",
    newProfileHeading: "New profile",
    profileName: "Name", profilePin: "PIN", addProfile: "Add profile",
    profileCreated: "Profile created. The PIN works once the lock has picked it up.",
    needProfileName: "Enter a name for the profile.",
    noProfiles: "No profiles on this lock.",
    cardsNote: "A profile holds permanent PINs and cards. A PIN is added here; for a card the lock is put in enrolment mode and you hold the card against the keypad.",
    refresh: "Refresh",
  },
  nl: {
    title: "Sloten",
    heading: "Toegangscodes",
    lock: "Slot",
    openDoor: "Deur openen",
    codesHeading: "Codes op dit slot",
    colName: "Naam", colFrom: "Geldig van", colUntil: "Geldig tot", colStatus: "Status",
    loading: "Laden…",
    newHeading: "Nieuwe code",
    name: "Naam", namePlaceholder: "Schoonmaker", pin: "Pincode",
    validFrom: "Geldig vanaf", validUntil: "Geldig tot",
    pattern: "Patroon",
    patContinuous: "Doorlopend geldig in die periode",
    patDaily: "Elke dag een vast tijdvenster",
    patDays: "Alleen op gekozen weekdagen",
    patOnce: "Eenmalig - vervalt na gebruik",
    days: "Dagen", dayFrom: "Elke dag vanaf", dayUntil: "Elke dag tot",
    create: "Code aanmaken",
    weekdays: ["ma", "di", "wo", "do", "vr", "za", "zo"],
    everyDay: "elke dag", singleUse: "eenmalig",
    noCodes: "Geen codes op dit slot.",
    remove: "Uit lijst", revoke: "Intrekken",
    confirmRemove: 'Record van "{name}" uit de lijst verwijderen?',
    confirmRevoke: 'Code "{name}" intrekken? Die werkt daarna niet meer.',
    removedOk: "Record verwijderd.", revokedOk: "Code ingetrokken.",
    failed: "Mislukt: {err}",
    confirmOpen: 'Het slot van "{name}" nu openen?',
    openedOk: "Deur geopend.",
    pinDigits: "Vul een pincode van alleen cijfers in.",
    needTimes: "Vul een begin- en eindtijd in.",
    needDay: "Kies minstens een weekdag.",
    needWindow: "Vul het dagelijkse tijdvenster in.",
    createdOk: "Code aangemaakt. Het duurt 1 tot 2 minuten voor het slot hem kent.",
    noLocks: "Nog geen sloten ingesteld. Voeg de integratie toe onder Instellingen → Apparaten & diensten.",
    revoked: "ingetrokken", expired: "verlopen", scheduled: "gepland", active: "actief",
    unconfirmed: "Het slot heeft de ontvangst van deze code niet bevestigd. Bij WiFi-keypads is dat normaal en werkt de code gewoon.",
    profilesHeading: "Profielen",
    colProfile: "Profiel", colMethods: "Ontgrendelmethodes",
    appAccount: "app-account", disabled: "uitgeschakeld",
    types: { password: "pincode", card: "pasje", fingerprint: "vingerafdruk", face: "gezicht" },
    addPin: "+ pincode", addCard: "+ pasje", rename: "hernoem",
    promptPin: "Pincode voor {name}:",
    promptMethodName: 'Naam voor deze methode (leeg = "{name}"):',
    promptRename: "Nieuwe naam voor {name}:",
    pinAdded: "Pincode toegevoegd. Hij werkt zodra het slot hem heeft opgepikt.",
    cardEnrolStarted: "Het slot wacht op een pasje: houd het nu tegen het paneel. Bij de volgende verversing staat het onder {name}.",
    methodRenamed: "Hernoemd.", methodRemoved: "Ontgrendelmethode verwijderd.",
    confirmRemoveMethod: '{type} "{name}" van {who} verwijderen?',
    disable: "Uitschakelen", enable: "Inschakelen",
    profileDisabled: "Profiel uitgeschakeld - de codes en pasjes ervan openen de deur niet meer.",
    profileEnabled: "Profiel ingeschakeld.",
    deleteProfile: "Profiel verwijderen",
    confirmDeleteProfile: 'Profiel "{name}" met al zijn ontgrendelmethodes verwijderen? Pasjes kun je alleen bij het apparaat opnieuw toevoegen.',
    profileDeleted: "Profiel verwijderd.",
    newProfileHeading: "Nieuw profiel",
    profileName: "Naam", profilePin: "Pincode", addProfile: "Profiel toevoegen",
    profileCreated: "Profiel aangemaakt. De pincode werkt zodra het slot hem heeft opgepikt.",
    needProfileName: "Vul een naam in voor het profiel.",
    noProfiles: "Geen profielen op dit slot.",
    cardsNote: "Een profiel heeft vaste pincodes en pasjes. Een pincode voeg je hier toe; voor een pasje wordt het slot in inschrijfmodus gezet en houd je het pasje tegen het paneel.",
    refresh: "Verversen",
  },
};

const CSS = `
  :host { display:block; padding:16px; font:14px/1.5 var(--paper-font-body1_-_font-family, system-ui, sans-serif);
          color:var(--primary-text-color); --line:var(--divider-color, #d5d8dd); --muted:var(--secondary-text-color, #6b7280);
          --accent:var(--primary-color, #03a9f4); max-width:1100px; margin:0 auto; }
  h1 { font-size:20px; margin:0 0 16px; }
  h2 { font-size:15px; margin:24px 0 8px; }
  .card { border:1px solid var(--line); border-radius:10px; padding:14px; margin-bottom:16px; background:var(--card-background-color, transparent); }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:7px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--muted); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.03em; }
  td.num { font-variant-numeric:tabular-nums; white-space:nowrap; }
  td small { color:var(--muted); display:block; }
  .tag { display:inline-block; padding:1px 8px; border-radius:99px; font-size:12px; border:1px solid var(--line); }
  .ok { color:#0a7c2f; border-color:#0a7c2f; } .wait { color:#b26a00; border-color:#b26a00; } .off { color:var(--muted); }
  label { display:block; font-size:12px; color:var(--muted); margin-bottom:3px; }
  input, select { width:100%; padding:7px 8px; border:1px solid var(--line); border-radius:6px; background:transparent;
                  color:var(--primary-text-color); font:inherit; box-sizing:border-box; }
  .row { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:10px; } .row > div { flex:1 1 150px; }
  button { padding:8px 14px; border:0; border-radius:6px; background:var(--accent); color:#fff; font:inherit; cursor:pointer; }
  button.sec { background:transparent; color:var(--accent); border:1px solid var(--accent); padding:4px 10px; }
  button.klein { padding:2px 8px; font-size:12px; } button:disabled { opacity:.5; cursor:default; }
  .dagen { display:flex; gap:6px; flex-wrap:wrap; }
  .dagen label { display:flex; align-items:center; gap:5px; margin:0; padding:6px 10px; border:1px solid var(--line);
                 border-radius:6px; color:var(--primary-text-color); font-size:13px; cursor:pointer; user-select:none; }
  .dagen input { width:auto; }
  .note { margin:0 0 10px; font-size:12px; color:var(--muted); }
  .methode { display:flex; align-items:center; gap:8px; padding:2px 0; flex-wrap:wrap; } .methode .tag { font-size:11px; }
  tr.uit td:first-child, tr.uit .methode span { color:var(--muted); }
  #msg { padding:10px 12px; border-radius:6px; margin-bottom:14px; display:none; }
  #msg.err { background:#fdecec; color:#8a1c1c; display:block; } #msg.good { background:#e8f5ec; color:#0a5c26; display:block; }
  .top { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; } .top > div:first-child { flex:1 1 200px; }
`;

const HTML = `
<h1 data-i18n="heading"></h1>
<div id="msg"></div>
<div class="card"><div class="top">
  <div><label for="lock" data-i18n="lock"></label><select id="lock"></select></div>
  <div><button id="open" data-i18n="openDoor"></button></div>
  <div><button id="refresh" class="sec" data-i18n="refresh"></button></div>
</div></div>

<h2 data-i18n="codesHeading"></h2>
<div class="card"><table><thead><tr>
  <th data-i18n="colName"></th><th data-i18n="colFrom"></th><th data-i18n="colUntil"></th><th data-i18n="colStatus"></th><th></th>
</tr></thead><tbody id="rows"></tbody></table></div>

<h2 data-i18n="newHeading"></h2>
<div class="card">
  <div class="row">
    <div><label for="naam" data-i18n="name"></label><input id="naam" data-i18n-ph="namePlaceholder"></div>
    <div><label for="pin" data-i18n="pin"></label><input id="pin" inputmode="numeric" placeholder="123456"></div>
  </div>
  <div class="row">
    <div><label for="van" data-i18n="validFrom"></label><input id="van" type="datetime-local"></div>
    <div><label for="tot" data-i18n="validUntil"></label><input id="tot" type="datetime-local"></div>
  </div>
  <div class="row"><div><label for="patroon" data-i18n="pattern"></label>
    <select id="patroon">
      <option value="doorlopend" data-i18n="patContinuous"></option>
      <option value="dagelijks" data-i18n="patDaily"></option>
      <option value="dagen" data-i18n="patDays"></option>
      <option value="eenmalig" data-i18n="patOnce"></option>
    </select></div></div>
  <div class="row" id="dagenrij" hidden><div style="flex:1 1 100%"><label data-i18n="days"></label><div id="dagen" class="dagen"></div></div></div>
  <div class="row" id="urenrij" hidden>
    <div><label for="dagvan" data-i18n="dayFrom"></label><input id="dagvan" type="time" value="11:00"></div>
    <div><label for="dagtot" data-i18n="dayUntil"></label><input id="dagtot" type="time" value="15:00"></div>
  </div>
  <button id="add" data-i18n="create"></button>
</div>

<h2 data-i18n="profilesHeading"></h2>
<div class="card">
  <p class="note" data-i18n="cardsNote"></p>
  <table><thead><tr><th data-i18n="colProfile"></th><th data-i18n="colMethods"></th><th></th></tr></thead>
  <tbody id="profielen"></tbody></table>
</div>

<h2 data-i18n="newProfileHeading"></h2>
<div class="card">
  <div class="row">
    <div><label for="pnaam" data-i18n="profileName"></label><input id="pnaam" data-i18n-ph="namePlaceholder"></div>
    <div><label for="ppin" data-i18n="profilePin"></label><input id="ppin" inputmode="numeric" placeholder="123456"></div>
  </div>
  <button id="padd" data-i18n="addProfile"></button>
</div>
`;

const fill = (s, v) => String(s).replace(/\{(\w+)\}/g, (_, k) => (v[k] !== undefined ? v[k] : ""));
const pad = (n) => String(n).padStart(2, "0");
const localIso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
// Tuya returns schedule hours as HHMM (1100 = 11:00) and the weekday mask with
// the bit order reversed from what was sent: Sunday 128, Monday 64 ... Saturday 2.
const RETURNED_BITS = [64, 32, 16, 8, 4, 2, 128];
const hhmm = (v) => String(v).padStart(4, "0").replace(/(\d\d)(\d\d)/, "$1:$2");

class TuyaLockBridgePanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._locks = [];
    this._built = false;
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._build();
  }
  get hass() { return this._hass; }

  // The same element doubles as a dashboard card: add this file as a
  // dashboard resource and use `type: custom:tuya-lock-bridge-panel`.
  setConfig(config) { this._config = config || {}; }
  getCardSize() { return 12; }

  // ------------------------------------------------------------- helpers
  get T() {
    const lang = (this._hass?.language || "en").slice(0, 2);
    return TEXT[lang] || TEXT.en;
  }
  $(id) { return this.shadowRoot.getElementById(id); }
  msg(text, kind) {
    const m = this.$("msg");
    m.textContent = text; m.className = kind;
    if (kind === "good") setTimeout(() => { m.className = ""; }, 6000);
  }
  async call(service, data, withResponse = false) {
    const res = await this._hass.callWS({
      type: "call_service", domain: "tuya_lock_bridge", service,
      service_data: { device_id: this.$("lock").value, ...data },
      return_response: withResponse,
    });
    return withResponse ? res.response : res;
  }
  fmt(iso) {
    const d = new Date(iso);
    const opts = { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" };
    if (d.getFullYear() !== new Date().getFullYear()) opts.year = "numeric";
    return d.toLocaleString(this._hass.language, opts);
  }

  // --------------------------------------------------------------- build
  _build() {
    const root = this.attachShadow({ mode: "open" });
    root.innerHTML = `<style>${CSS}</style>${HTML}`;
    const T = this.T;
    root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = T[el.dataset.i18n] || ""; });
    root.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = T[el.dataset.i18nPh] || ""; });

    this.$("dagen").innerHTML = T.weekdays.map((d, i) =>
      `<label><input type="checkbox" value="${i + 1}" checked>${d}</label>`).join("");
    const showPattern = () => {
      const p = this.$("patroon").value;
      this.$("dagenrij").hidden = p !== "dagen";
      this.$("urenrij").hidden = p !== "dagen" && p !== "dagelijks";
    };
    this.$("patroon").onchange = showPattern; showPattern();

    const now = new Date(), tomorrow = new Date(Date.now() + 864e5);
    tomorrow.setHours(12, 0, 0, 0);
    this.$("van").value = localIso(now); this.$("tot").value = localIso(tomorrow);

    this.$("lock").onchange = () => this.reload();
    this.$("refresh").onclick = () => this.reload(true);
    this.$("open").onclick = () => this.openDoor();
    this.$("add").onclick = () => this.createCode();
    this.$("padd").onclick = () => this.addProfile();

    this._loadLocks();
  }

  async _loadLocks() {
    const devices = await this._hass.callWS({ type: "config/device_registry/list" });
    this._locks = devices
      .filter((d) => d.identifiers.some((i) => i[0] === "tuya_lock_bridge"))
      .map((d) => ({ id: d.id, name: d.name_by_user || d.name }))
      .sort((a, b) => a.name.localeCompare(b.name));
    if (!this._locks.length) { this.msg(this.T.noLocks, "err"); return; }
    this.$("lock").innerHTML = this._locks.map((l) => `<option value="${l.id}">${l.name}</option>`).join("");
    this.reload();
  }

  lockName() { const l = this._locks.find((x) => x.id === this.$("lock").value); return l ? l.name : ""; }

  async reload(ask = false) {
    if (ask) { try { await this.call("refresh", {}); } catch (e) { /* the lists below tell the story */ } }
    await Promise.all([this.loadCodes(), this.loadProfiles()]);
  }

  // --------------------------------------------------------------- codes
  status(c, now) {
    if (c.phase === 17) return ["revoked", "off"];
    if (c.invalid_time < now) return ["expired", "off"];
    if (c.effective_time > now) return ["scheduled", "wait"];
    return ["active", "ok"];
  }
  patternText(c) {
    const T = this.T, s = (c.schedule_list || [])[0];
    const once = c.type === 1 ? T.singleUse : "";
    if (!s) return once;
    const days = T.weekdays.filter((_, i) => s.working_day & RETURNED_BITS[i]);
    const which = days.length === 7 ? T.everyDay : days.join(" ");
    return [`${which} ${hhmm(s.effective_time)}-${hhmm(s.invalid_time)}`, once].filter(Boolean).join(", ");
  }
  async loadCodes() {
    const T = this.T, rows = this.$("rows");
    rows.innerHTML = `<tr><td colspan="5">${T.loading}</td></tr>`;
    try {
      const { codes } = await this.call("list_codes", {}, true);
      const now = Math.floor(Date.now() / 1000);
      const list = (codes || []).slice().sort((a, b) => b.effective_time - a.effective_time);
      rows.innerHTML = list.length ? "" : `<tr><td colspan="5">${T.noCodes}</td></tr>`;
      for (const c of list) {
        const [key, cls] = this.status(c, now);
        const tr = document.createElement("tr");
        tr.innerHTML = `<td></td><td class="num">${this.fmt(c.effective_time * 1000)}</td><td class="num">${this.fmt(c.invalid_time * 1000)}</td>
          <td><span class="tag ${cls}" ${key === "active" && c.phase === 12 ? `title="${T.unconfirmed}"` : ""}>${T[key]}${key === "active" && c.phase === 12 ? " °" : ""}</span></td><td style="text-align:right"></td>`;
        tr.firstElementChild.textContent = c.name;
        const p = this.patternText(c);
        if (p) { const s = document.createElement("small"); s.textContent = p; tr.firstElementChild.appendChild(s); }
        const gone = c.invalid_time < now || c.phase === 17;
        const b = document.createElement("button");
        b.className = "sec"; b.textContent = gone ? T.remove : T.revoke;
        b.onclick = async () => {
          if (!confirm(fill(gone ? T.confirmRemove : T.confirmRevoke, { name: c.name }))) return;
          b.disabled = true;
          try { await this.call(gone ? "purge_code" : "revoke_code", { code_id: c.id }); this.msg(gone ? T.removedOk : T.revokedOk, "good"); this.loadCodes(); }
          catch (e) { this.msg(fill(T.failed, { err: e.message }), "err"); b.disabled = false; }
        };
        tr.lastElementChild.appendChild(b);
        rows.appendChild(tr);
      }
    } catch (e) {
      this.msg(fill(T.failed, { err: e.message }), "err"); rows.innerHTML = "";
    }
  }
  async openDoor() {
    const T = this.T;
    if (!confirm(fill(T.confirmOpen, { name: this.lockName() }))) return;
    this.$("open").disabled = true;
    try { await this.call("unlock", {}); this.msg(T.openedOk, "good"); }
    catch (e) { this.msg(fill(T.failed, { err: e.message }), "err"); }
    this.$("open").disabled = false;
  }
  async createCode() {
    const T = this.T, pin = this.$("pin").value.trim(), van = this.$("van").value, tot = this.$("tot").value;
    if (!/^[0-9]+$/.test(pin)) return this.msg(T.pinDigits, "err");
    if (!van || !tot) return this.msg(T.needTimes, "err");
    const data = { password: pin, name: this.$("naam").value.trim() || undefined, start: van, end: tot };
    const p = this.$("patroon").value;
    if (p === "eenmalig") data.one_time = true;
    else if (p === "dagelijks" || p === "dagen") {
      const days = p === "dagelijks" ? [1, 2, 3, 4, 5, 6, 7]
        : [...this.$("dagen").querySelectorAll("input:checked")].map((i) => Number(i.value));
      if (!days.length) return this.msg(T.needDay, "err");
      if (!this.$("dagvan").value || !this.$("dagtot").value) return this.msg(T.needWindow, "err");
      Object.assign(data, { days, daily_from: this.$("dagvan").value, daily_until: this.$("dagtot").value });
    }
    this.$("add").disabled = true;
    try { await this.call("create_code", data); this.msg(T.createdOk, "good"); this.$("naam").value = ""; this.$("pin").value = ""; this.loadCodes(); }
    catch (e) { this.msg(fill(T.failed, { err: e.message }), "err"); }
    this.$("add").disabled = false;
  }

  // ------------------------------------------------------------ profiles
  async loadProfiles() {
    const T = this.T, tbody = this.$("profielen");
    tbody.innerHTML = `<tr><td colspan="3">${T.loading}</td></tr>`;
    try {
      const { profiles } = await this.call("list_profiles", {}, true);
      tbody.innerHTML = profiles.length ? "" : `<tr><td colspan="3">${T.noProfiles}</td></tr>`;
      for (const m of profiles) {
        const tr = document.createElement("tr");
        if (m.active === false) tr.className = "uit";
        const name = document.createElement("td");
        name.textContent = m.name || m.user_id;
        if (m.home_user || m.active === false) {
          const s = document.createElement("small"); s.textContent = m.home_user ? T.appAccount : T.disabled; name.appendChild(s);
        }
        const methods = document.createElement("td");
        for (const x of m.methods) {
          const row = document.createElement("div"); row.className = "methode";
          const tag = document.createElement("span"); tag.className = "tag"; tag.textContent = T.types[x.type] || x.type;
          const txt = document.createElement("span"); txt.textContent = x.name || `#${x.sn}`;
          row.append(tag, txt);
          if (!m.home_user) {
            row.append(this.smallButton(T.rename, async (b) => {
              const n = prompt(fill(T.promptRename, { name: x.name || `#${x.sn}` }), x.name || "");
              if (n === null || !n.trim()) return;
              await this.act(b, "rename_method", { user_id: m.user_id, type: x.type, sn: x.sn, name: n.trim() }, T.methodRenamed);
            }));
            row.append(this.smallButton(T.remove, async (b) => {
              if (!confirm(fill(T.confirmRemoveMethod, { type: T.types[x.type] || x.type, name: x.name || `#${x.sn}`, who: m.name }))) return;
              await this.act(b, "delete_method", { user_id: m.user_id, type: x.type, sn: x.sn }, T.methodRemoved);
            }));
          }
          methods.appendChild(row);
        }
        if (!m.home_user) {
          const row = document.createElement("div"); row.className = "methode";
          row.append(this.smallButton(T.addPin, async (b) => {
            const pin = prompt(fill(T.promptPin, { name: m.name }));
            if (pin === null) return;
            if (!/^[0-9]+$/.test(pin.trim())) return this.msg(T.pinDigits, "err");
            const n = prompt(fill(T.promptMethodName, { name: m.name }));
            if (n === null) return;
            await this.act(b, "add_method", { user_id: m.user_id, type: "password", password: pin.trim(), name: n.trim() || undefined }, T.pinAdded);
          }));
          row.append(this.smallButton(T.addCard, async (b) => {
            await this.act(b, "add_method", { user_id: m.user_id, type: "card" }, fill(T.cardEnrolStarted, { name: m.name }), false);
          }));
          methods.appendChild(row);
        }
        const actions = document.createElement("td"); actions.style.textAlign = "right";
        if (!m.home_user) {
          const sw = document.createElement("button"); sw.className = "sec"; sw.style.marginRight = "6px";
          sw.textContent = m.active === false ? T.enable : T.disable;
          sw.onclick = async () => {
            const entity = Object.values(this._hass.states).find((s) => s.attributes.user_id === m.user_id && s.entity_id.startsWith("switch."));
            if (!entity) return;
            sw.disabled = true;
            try {
              await this._hass.callService("switch", m.active === false ? "turn_on" : "turn_off", {}, { entity_id: entity.entity_id });
              this.msg(m.active === false ? T.profileEnabled : T.profileDisabled, "good"); this.loadProfiles();
            } catch (e) { this.msg(fill(T.failed, { err: e.message }), "err"); sw.disabled = false; }
          };
          const del = document.createElement("button"); del.className = "sec"; del.textContent = T.deleteProfile;
          del.onclick = async () => {
            if (!confirm(fill(T.confirmDeleteProfile, { name: m.name }))) return;
            await this.act(del, "delete_profile", { user_id: m.user_id }, T.profileDeleted);
          };
          actions.append(sw, del);
        }
        tr.append(name, methods, actions);
        tbody.appendChild(tr);
      }
    } catch (e) {
      this.msg(fill(T.failed, { err: e.message }), "err"); tbody.innerHTML = "";
    }
  }
  smallButton(text, onClick) {
    const b = document.createElement("button"); b.className = "sec klein"; b.textContent = text;
    b.onclick = () => onClick(b); return b;
  }
  async act(button, service, data, okText, reload = true) {
    button.disabled = true;
    try { await this.call(service, data); this.msg(okText, "good"); if (reload) this.loadProfiles(); }
    catch (e) { this.msg(fill(this.T.failed, { err: e.message }), "err"); }
    button.disabled = false;
  }
  async addProfile() {
    const T = this.T, name = this.$("pnaam").value.trim(), pin = this.$("ppin").value.trim();
    if (!name) return this.msg(T.needProfileName, "err");
    if (!/^[0-9]+$/.test(pin)) return this.msg(T.pinDigits, "err");
    this.$("padd").disabled = true;
    try { await this.call("add_profile", { name, password: pin }); this.msg(T.profileCreated, "good"); this.$("pnaam").value = ""; this.$("ppin").value = ""; this.loadProfiles(); }
    catch (e) { this.msg(fill(T.failed, { err: e.message }), "err"); }
    this.$("padd").disabled = false;
  }
}

customElements.define("tuya-lock-bridge-panel", TuyaLockBridgePanel);
