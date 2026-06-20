/* ============================================================
   Kayendar — SPA JavaScript
   Vanilla JS, no dependencies.
   Handles: auth, routing, calendar (month/week), contacts,
            collection management, modals, iCal/vCard parsing.
   ============================================================ */

'use strict';

// ── API helpers ──────────────────────────────────────────────
const api = {
  async req(method, path, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    let data;
    try { data = await res.json(); } catch { data = null; }
    if (!res.ok) throw new Error(data?.error || res.statusText);
    return data;
  },
  get:    (p)    => api.req('GET',    p),
  post:   (p, b) => api.req('POST',   p, b),
  put:    (p, b) => api.req('PUT',    p, b),
  patch:  (p, b) => api.req('PATCH',  p, b),
  delete: (p)    => api.req('DELETE', p),
};

// ── Toast ────────────────────────────────────────────────────
function toast(message, type = 'success') {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `<div class="toast-dot"></div><span>${message}</span>`;
  c.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; t.style.transition = '0.3s'; setTimeout(() => t.remove(), 300); }, 3000);
}

// ── State ────────────────────────────────────────────────────
const state = {
  user: null,
  collections: [],
  events: {},   // slug -> [parsed event objects]
  contacts: {}, // slug -> [parsed contact objects]
  calView: 'month',
  calDate: new Date(),
  activeView: 'calendar',
};

// ── iCal helpers ─────────────────────────────────────────────
function parseIcs(content) {
  const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const events = [];
  let cur = null;
  let inAlarm = false;
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line === 'BEGIN:VEVENT') { cur = {}; continue; }
    if (line === 'END:VEVENT') { if (cur) { events.push(cur); cur = null; } continue; }
    if (line === 'BEGIN:VALARM') { inAlarm = true; continue; }
    if (line === 'END:VALARM') { inAlarm = false; continue; }
    if (!cur) continue;
    const colon = line.indexOf(':');
    if (colon < 0) continue;
    const key = line.slice(0, colon).split(';')[0].toUpperCase();
    const val = line.slice(colon + 1);
    if (key === 'DTSTART')   cur.start = parseIcsDate(val);
    if (key === 'DTEND')     cur.end   = parseIcsDate(val);
    if (key === 'SUMMARY')   cur.title = val;
    if (key === 'DESCRIPTION' && !inAlarm) cur.description = val;
    if (key === 'LOCATION')    cur.location = val;
    if (key === 'TRIGGER' && inAlarm) cur.alarm = val;
    if (key === 'UID')       cur.uid = val;
  }
  return events;
}

function parseIcsDate(val) {
  // 20240115T120000Z or 20240115T120000 or 20240115
  const s = val.replace(/Z$/, '');
  if (s.length === 8) {
    return new Date(+s.slice(0,4), +s.slice(4,6)-1, +s.slice(6,8));
  }
  return new Date(
    +s.slice(0,4), +s.slice(4,6)-1, +s.slice(6,8),
    +s.slice(9,11), +s.slice(11,13), +s.slice(13,15)
  );
}

function formatIcsDate(d, allDay = false) {
  const pad = n => String(n).padStart(2,'0');
  const y = d.getFullYear(), mo = pad(d.getMonth()+1), dd = pad(d.getDate());
  if (allDay) return `${y}${mo}${dd}`;
  const h = pad(d.getHours()), mi = pad(d.getMinutes()), s = pad(d.getSeconds());
  return `${y}${mo}${dd}T${h}${mi}${s}`;
}

function buildIcs(uid, title, start, end, description = '', location = '', alarm = '') {
  const now = formatIcsDate(new Date()) + 'Z';
  const alarmLines = alarm ? [
    'BEGIN:VALARM',
    'ACTION:DISPLAY',
    `TRIGGER:${alarm}`,
    `DESCRIPTION:${title}`,
    'END:VALARM'
  ] : [];
  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Kayendar//EN',
    'BEGIN:VEVENT',
    `UID:${uid}`,
    `DTSTAMP:${now}`,
    `DTSTART:${formatIcsDate(start)}`,
    `DTEND:${formatIcsDate(end)}`,
    `SUMMARY:${title}`,
    description ? `DESCRIPTION:${description}` : '',
    location ? `LOCATION:${location}` : '',
    ...alarmLines,
    'END:VEVENT',
    'END:VCALENDAR',
  ].filter(Boolean).join('\r\n') + '\r\n';
}

// ── vCard helpers ────────────────────────────────────────────
function parseVcf(content) {
  const contacts = [];
  const cards = content.split(/BEGIN:VCARD/i).slice(1);
  for (const card of cards) {
    const c = {};
    for (const line of card.split(/\r?\n/)) {
      const colon = line.indexOf(':');
      if (colon < 0) continue;
      const key = line.slice(0, colon).split(';')[0].toUpperCase();
      const val = line.slice(colon + 1).trim();
      if (key === 'FN') c.fn = val;
      if (key === 'N') {
        const parts = val.split(';');
        c.lastName  = parts[0] || '';
        c.firstName = parts[1] || '';
      }
      if (key === 'EMAIL') c.email = val;
      if (key === 'TEL')   c.phone = val;
      if (key === 'UID')   c.uid   = val;
    }
    if (c.fn || c.firstName || c.lastName) contacts.push(c);
  }
  return contacts;
}

function buildVcf(uid, firstName, lastName, email, phone) {
  return [
    'BEGIN:VCARD',
    'VERSION:3.0',
    `UID:${uid}`,
    `FN:${firstName} ${lastName}`.trim(),
    `N:${lastName};${firstName};;;`,
    email ? `EMAIL:${email}` : '',
    phone ? `TEL:${phone}` : '',
    'END:VCARD',
  ].filter(Boolean).join('\r\n') + '\r\n';
}

function generateUid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random()*16|0;
    return (c==='x' ? r : (r&0x3|0x8)).toString(16);
  });
}

// ── Load all data ────────────────────────────────────────────
async function loadAllData() {
  state.collections = await api.get('/api/collections');
  state.events = {};
  state.contacts = {};

  for (const col of state.collections) {
    try {
      const items = await api.get(`/api/collections/${col.slug}/items`);
      if (col.type === 'calendar') {
        state.events[col.slug] = items.flatMap(i => {
          const evs = parseIcs(i.content);
          return evs.map(e => ({ ...e, filename: i.filename, collectionSlug: col.slug, collectionColor: col.color }));
        });
      } else {
        state.contacts[col.slug] = items.flatMap(i => {
          const cs = parseVcf(i.content);
          return cs.map(c => ({ ...c, filename: i.filename, collectionSlug: col.slug }));
        });
      }
    } catch { /* skip */ }
  }
}

// ── Collections sidebar ──────────────────────────────────────
function renderSidebar() {
  const calList = document.getElementById('calendars-list');
  const abList  = document.getElementById('addressbooks-list');
  calList.innerHTML = '';
  abList.innerHTML  = '';

  for (const col of state.collections) {
    const el = document.createElement('div');
    el.className = 'collection-item active';
    el.dataset.slug = col.slug;
    el.innerHTML = `
      <span class="collection-dot" style="background:${col.color}"></span>
      <span class="collection-name">${col.display_name}</span>
      <button class="collection-edit-btn" data-slug="${col.slug}" title="Edit">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
      </button>`;

    el.querySelector('.collection-edit-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      openEditCollection(col);
    });

    if (col.type === 'calendar') calList.appendChild(el);
    else abList.appendChild(el);
  }
}

// ── Calendar rendering ───────────────────────────────────────
function allEvents() {
  return Object.values(state.events).flat();
}

function renderCalendar() {
  const grid = document.getElementById('calendar-grid');
  grid.innerHTML = '';

  if (state.calView === 'month') renderMonthView(grid);
  else renderWeekView(grid);
}

function renderMonthView(grid) {
  const date = state.calDate;
  const year = date.getFullYear(), month = date.getMonth();
  document.getElementById('cal-title').textContent =
    new Date(year, month, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' });

  const firstDay = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month+1, 0).getDate();
  const today = new Date();

  const weekdays = document.createElement('div');
  weekdays.className = 'cal-weekdays';
  ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].forEach(d => {
    const el = document.createElement('div');
    el.className = 'cal-weekday';
    el.textContent = d;
    weekdays.appendChild(el);
  });
  grid.appendChild(weekdays);

  const body = document.createElement('div');
  body.className = 'cal-body';

  // Previous month days
  const prevMonthDays = new Date(year, month, 0).getDate();
  for (let i = firstDay - 1; i >= 0; i--) {
    body.appendChild(createDayCell(new Date(year, month-1, prevMonthDays-i), true));
  }
  // Current month
  for (let d = 1; d <= daysInMonth; d++) {
    body.appendChild(createDayCell(new Date(year, month, d), false));
  }
  // Next month days
  const total = firstDay + daysInMonth;
  const nextDays = (7 - (total % 7)) % 7;
  for (let d = 1; d <= nextDays; d++) {
    body.appendChild(createDayCell(new Date(year, month+1, d), true));
  }

  grid.appendChild(body);
}

function createDayCell(date, otherMonth) {
  const today = new Date();
  const isToday = date.toDateString() === today.toDateString();
  const cell = document.createElement('div');
  cell.className = 'cal-day' + (otherMonth ? ' cal-day--other-month' : '') + (isToday ? ' cal-day--today' : '');

  const num = document.createElement('div');
  num.className = 'cal-day-num';
  num.textContent = date.getDate();
  cell.appendChild(num);

  // Events for this day
  const dayEvents = allEvents().filter(e => e.start && isSameDay(e.start, date));
  if (dayEvents.length) {
    const evContainer = document.createElement('div');
    evContainer.className = 'cal-events';
    const show = dayEvents.slice(0, 3);
    show.forEach(ev => {
      const evEl = document.createElement('div');
      evEl.className = 'cal-event';
      evEl.textContent = ev.title || '(no title)';
      evEl.style.background = (ev.collectionColor || '#6366f1') + '33';
      evEl.style.color = ev.collectionColor || '#818cf8';
      evEl.title = ev.title;
      evEl.addEventListener('click', e => { e.stopPropagation(); openEditEvent(ev); });
      evContainer.appendChild(evEl);
    });
    if (dayEvents.length > 3) {
      const more = document.createElement('div');
      more.className = 'cal-more';
      more.textContent = `+${dayEvents.length - 3} more`;
      evContainer.appendChild(more);
    }
    cell.appendChild(evContainer);
  }

  cell.addEventListener('click', () => openNewEvent(date));
  return cell;
}

function isSameDay(a, b) {
  return a.getFullYear() === b.getFullYear() &&
         a.getMonth() === b.getMonth() &&
         a.getDate() === b.getDate();
}

function renderWeekView(grid) {
  const date = state.calDate;
  const dow = date.getDay();
  const weekStart = new Date(date); weekStart.setDate(date.getDate() - dow);
  const weekEnd = new Date(weekStart); weekEnd.setDate(weekStart.getDate() + 6);

  document.getElementById('cal-title').textContent =
    `${weekStart.toLocaleDateString('en-US', {month:'short', day:'numeric'})} – ${weekEnd.toLocaleDateString('en-US', {month:'short', day:'numeric', year:'numeric'})}`;

  const today = new Date();
  const weekGrid = document.createElement('div');
  weekGrid.className = 'week-grid';

  // Time column
  const timeCol = document.createElement('div');
  timeCol.className = 'week-time-col';
  const timeHeader = document.createElement('div');
  timeHeader.style.cssText = 'height:40px; border-bottom:1px solid var(--glass-border);';
  timeCol.appendChild(timeHeader);
  for (let h = 0; h < 24; h++) {
    const slot = document.createElement('div');
    slot.className = 'week-time-slot';
    slot.textContent = h === 0 ? '' : `${h}:00`;
    timeCol.appendChild(slot);
  }
  weekGrid.appendChild(timeCol);

  // Day columns
  for (let d = 0; d < 7; d++) {
    const dayDate = new Date(weekStart); dayDate.setDate(weekStart.getDate() + d);
    const isToday = dayDate.toDateString() === today.toDateString();

    const col = document.createElement('div');
    col.className = 'week-day-col';

    const header = document.createElement('div');
    header.className = 'week-day-header' + (isToday ? ' today' : '');
    header.textContent = dayDate.toLocaleDateString('en-US', {weekday:'short', day:'numeric'});
    col.appendChild(header);

    const eventsArea = document.createElement('div');
    eventsArea.className = 'week-day-events';

    // Hour lines
    for (let h = 0; h < 24; h++) {
      const line = document.createElement('div');
      line.className = 'week-hour-line';
      line.style.top = `${h * 56}px`;
      eventsArea.appendChild(line);
    }

    // Events
    const dayEvents = allEvents().filter(e => e.start && isSameDay(e.start, dayDate));
    dayEvents.forEach(ev => {
      const startH = ev.start.getHours() + ev.start.getMinutes()/60;
      const endH   = ev.end ? ev.end.getHours() + ev.end.getMinutes()/60 : startH + 1;
      const top    = startH * 56;
      const height = Math.max((endH - startH) * 56, 20);

      const evEl = document.createElement('div');
      evEl.className = 'week-event';
      evEl.textContent = ev.title || '(no title)';
      evEl.style.top = `${top}px`;
      evEl.style.height = `${height}px`;
      evEl.style.background = (ev.collectionColor || '#6366f1') + '44';
      evEl.style.color = ev.collectionColor || '#818cf8';
      evEl.style.borderLeft = `3px solid ${ev.collectionColor || '#6366f1'}`;
      evEl.addEventListener('click', () => openEditEvent(ev));
      eventsArea.appendChild(evEl);
    });

    col.appendChild(eventsArea);
    col.addEventListener('click', (e) => {
      if (e.target === col || e.target === eventsArea) openNewEvent(dayDate);
    });
    weekGrid.appendChild(col);
  }

  grid.appendChild(weekGrid);
}

// ── Contacts rendering ───────────────────────────────────────
function allContacts() {
  return Object.values(state.contacts).flat();
}

function renderContacts() {
  const grid = document.getElementById('contacts-grid');
  const search = document.getElementById('contacts-search').value.toLowerCase();
  grid.innerHTML = '';

  let contacts = allContacts();
  if (search) {
    contacts = contacts.filter(c =>
      (c.fn || '').toLowerCase().includes(search) ||
      (c.firstName || '').toLowerCase().includes(search) ||
      (c.lastName || '').toLowerCase().includes(search) ||
      (c.email || '').toLowerCase().includes(search)
    );
  }

  if (!contacts.length) {
    const empty = document.createElement('div');
    empty.className = 'contact-empty';
    empty.textContent = search ? 'No contacts found.' : 'No contacts yet. Add your first contact!';
    grid.appendChild(empty);
    return;
  }

  contacts.forEach(c => {
    const name = c.fn || `${c.firstName || ''} ${c.lastName || ''}`.trim() || '?';
    const initials = name.split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase();
    const colors = ['#6366f1','#ec4899','#f59e0b','#10b981','#3b82f6','#8b5cf6','#06b6d4'];
    const color = colors[(name.charCodeAt(0) || 0) % colors.length];

    const card = document.createElement('div');
    card.className = 'contact-card';
    card.innerHTML = `
      <div class="contact-avatar" style="background:${color}">${initials}</div>
      <div class="contact-name">${name}</div>
      ${c.email ? `<div class="contact-email">${c.email}</div>` : ''}
      ${c.phone ? `<div class="contact-phone">${c.phone}</div>` : ''}
    `;
    card.addEventListener('click', () => openEditContact(c));
    grid.appendChild(card);
  });
}

// ── Modal helpers ────────────────────────────────────────────
function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
}
function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
}

// ── Event modal ───────────────────────────────────────────────
function openNewEvent(date) {
  const form = document.getElementById('event-form');
  form.reset();
  document.getElementById('event-modal-title').textContent = 'New Event';
  document.getElementById('event-uid').value = '';
  document.getElementById('event-filename').value = '';
  document.getElementById('event-collection').value = '';
  document.getElementById('event-delete-btn').classList.add('hidden');

  // Default times
  const start = new Date(date);
  start.setHours(9,0,0,0);
  const end = new Date(start);
  end.setHours(10,0,0,0);
  document.getElementById('event-start').value = toDatetimeLocal(start);
  document.getElementById('event-end').value   = toDatetimeLocal(end);

  populateCalendarSelect('event-calendar');
  openModal('event-modal');
}

function openEditEvent(ev) {
  document.getElementById('event-modal-title').textContent = 'Edit Event';
  document.getElementById('event-uid').value = ev.uid || '';
  document.getElementById('event-filename').value = ev.filename || '';
  document.getElementById('event-collection').value = ev.collectionSlug || '';
  document.getElementById('event-title').value = ev.title || '';
  document.getElementById('event-location').value = ev.location || '';
  
  // Handle alarm/reminder field
  const alarmSelect = document.getElementById('event-alarm');
  const standardAlarms = ['', 'PT0S', '-PT5M', '-PT15M', '-PT30M', '-PT1H', '-PT2H', '-P1D'];
  for (let i = alarmSelect.options.length - 1; i >= 0; i--) {
    if (!standardAlarms.includes(alarmSelect.options[i].value)) {
      alarmSelect.remove(i);
    }
  }
  let alarmValue = ev.alarm || '';
  let optionExists = false;
  for (let i = 0; i < alarmSelect.options.length; i++) {
    if (alarmSelect.options[i].value === alarmValue) {
      optionExists = true;
      break;
    }
  }
  if (alarmValue && !optionExists) {
    const newOpt = document.createElement('option');
    newOpt.value = alarmValue;
    newOpt.text = `Custom (${alarmValue})`;
    alarmSelect.add(newOpt);
  }
  alarmSelect.value = alarmValue;

  document.getElementById('event-description').value = ev.description || '';
  if (ev.start) document.getElementById('event-start').value = toDatetimeLocal(ev.start);
  if (ev.end)   document.getElementById('event-end').value   = toDatetimeLocal(ev.end);
  document.getElementById('event-delete-btn').classList.remove('hidden');
  populateCalendarSelect('event-calendar', ev.collectionSlug);
  openModal('event-modal');
}

function toDatetimeLocal(d) {
  const pad = n => String(n).padStart(2,'0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function populateCalendarSelect(selectId, selectedSlug) {
  const sel = document.getElementById(selectId);
  const cals = state.collections.filter(c => c.type === 'calendar');
  sel.innerHTML = cals.map(c =>
    `<option value="${c.slug}" ${c.slug === selectedSlug ? 'selected' : ''}>${c.display_name}</option>`
  ).join('');
}

function populateAddressbookSelect(selectId, selectedSlug) {
  const sel = document.getElementById(selectId);
  const abs = state.collections.filter(c => c.type === 'addressbook');
  sel.innerHTML = abs.map(c =>
    `<option value="${c.slug}" ${c.slug === selectedSlug ? 'selected' : ''}>${c.display_name}</option>`
  ).join('');
}

async function saveEvent(e) {
  e.preventDefault();
  const title = document.getElementById('event-title').value.trim();
  const start = new Date(document.getElementById('event-start').value);
  const end   = new Date(document.getElementById('event-end').value);
  const location = document.getElementById('event-location').value.trim();
  const alarm    = document.getElementById('event-alarm').value;
  const description = document.getElementById('event-description').value.trim();
  const slug  = document.getElementById('event-calendar').value;
  let uid     = document.getElementById('event-uid').value;
  let filename = document.getElementById('event-filename').value;

  if (!title) { toast('Title is required', 'error'); return; }
  if (!slug)  { toast('Please select a calendar', 'error'); return; }

  if (!uid) uid = generateUid();
  if (!filename) filename = uid + '.ics';

  const content = buildIcs(uid, title, start, end, description, location, alarm);

  try {
    await api.put(`/api/collections/${slug}/items/${filename}`, { content });
    toast('Event saved');
    closeModal('event-modal');
    await loadAllData();
    renderCalendar();
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function deleteEvent() {
  const slug     = document.getElementById('event-collection').value || document.getElementById('event-calendar').value;
  const filename = document.getElementById('event-filename').value;
  if (!filename) return;
  try {
    await api.delete(`/api/collections/${slug}/items/${filename}`);
    toast('Event deleted');
    closeModal('event-modal');
    await loadAllData();
    renderCalendar();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Contact modal ─────────────────────────────────────────────
function openNewContact() {
  document.getElementById('contact-form').reset();
  document.getElementById('contact-modal-title').textContent = 'New Contact';
  document.getElementById('contact-uid').value = '';
  document.getElementById('contact-filename').value = '';
  document.getElementById('contact-collection').value = '';
  document.getElementById('contact-delete-btn').classList.add('hidden');
  populateAddressbookSelect('contact-addressbook');
  openModal('contact-modal');
}

function openEditContact(c) {
  document.getElementById('contact-modal-title').textContent = 'Edit Contact';
  document.getElementById('contact-uid').value = c.uid || '';
  document.getElementById('contact-filename').value = c.filename || '';
  document.getElementById('contact-collection').value = c.collectionSlug || '';
  document.getElementById('contact-firstname').value = c.firstName || '';
  document.getElementById('contact-lastname').value  = c.lastName  || '';
  document.getElementById('contact-email').value     = c.email     || '';
  document.getElementById('contact-phone').value     = c.phone     || '';
  document.getElementById('contact-delete-btn').classList.remove('hidden');
  populateAddressbookSelect('contact-addressbook', c.collectionSlug);
  openModal('contact-modal');
}

async function saveContact(e) {
  e.preventDefault();
  const firstName = document.getElementById('contact-firstname').value.trim();
  const lastName  = document.getElementById('contact-lastname').value.trim();
  const email     = document.getElementById('contact-email').value.trim();
  const phone     = document.getElementById('contact-phone').value.trim();
  const slug      = document.getElementById('contact-addressbook').value;
  let uid      = document.getElementById('contact-uid').value;
  let filename = document.getElementById('contact-filename').value;

  if (!lastName && !firstName) { toast('Name is required', 'error'); return; }
  if (!slug) { toast('Please select an address book', 'error'); return; }

  if (!uid) uid = generateUid();
  if (!filename) filename = uid + '.vcf';

  const content = buildVcf(uid, firstName, lastName, email, phone);

  try {
    await api.put(`/api/collections/${slug}/items/${filename}`, { content });
    toast('Contact saved');
    closeModal('contact-modal');
    await loadAllData();
    renderContacts();
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function deleteContact() {
  const slug     = document.getElementById('contact-collection').value || document.getElementById('contact-addressbook').value;
  const filename = document.getElementById('contact-filename').value;
  if (!filename) return;
  try {
    await api.delete(`/api/collections/${slug}/items/${filename}`);
    toast('Contact deleted');
    closeModal('contact-modal');
    await loadAllData();
    renderContacts();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Collection modal ──────────────────────────────────────────
function openNewCollection(type) {
  document.getElementById('collection-form').reset();
  document.getElementById('collection-modal-title').textContent = type === 'calendar' ? 'New Calendar' : 'New Address Book';
  document.getElementById('col-type').value = type;
  document.getElementById('col-slug').value = '';
  document.getElementById('col-color').value = type === 'calendar' ? '#6366f1' : '#10b981';
  document.getElementById('col-delete-btn').classList.add('hidden');
  openModal('collection-modal');
}

function openEditCollection(col) {
  document.getElementById('collection-modal-title').textContent = 'Edit Collection';
  document.getElementById('col-name').value  = col.display_name;
  document.getElementById('col-color').value = col.color;
  document.getElementById('col-type').value  = col.type;
  document.getElementById('col-slug').value  = col.slug;
  document.getElementById('col-delete-btn').classList.remove('hidden');
  openModal('collection-modal');
}

async function saveCollection(e) {
  e.preventDefault();
  const name  = document.getElementById('col-name').value.trim();
  const color = document.getElementById('col-color').value;
  const type  = document.getElementById('col-type').value;
  const slug  = document.getElementById('col-slug').value;

  if (!name) { toast('Name is required', 'error'); return; }

  try {
    if (slug) {
      await api.patch(`/api/collections/${slug}`, { display_name: name, color });
      toast('Collection updated');
    } else {
      await api.post('/api/collections', { display_name: name, color, type });
      toast('Collection created');
    }
    closeModal('collection-modal');
    await loadAllData();
    renderSidebar();
    renderCalendar();
  } catch (err) {
    toast(err.message, 'error');
  }
}

async function deleteCollection() {
  const slug = document.getElementById('col-slug').value;
  if (!slug) return;
  if (!confirm('Delete this collection and all its items?')) return;
  try {
    await api.delete(`/api/collections/${slug}`);
    toast('Collection deleted');
    closeModal('collection-modal');
    await loadAllData();
    renderSidebar();
    renderCalendar();
    renderContacts();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Navigation ────────────────────────────────────────────────
function switchView(view) {
  state.activeView = view;
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.getElementById(`view-${view}`).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
  document.getElementById(`nav-${view}`).classList.add('active');
  if (view === 'contacts') renderContacts();
  if (view === 'calendar') renderCalendar();
}

// ── Auth flow ────────────────────────────────────────────────
async function checkAuth() {
  try {
    const data = await api.get('/api/me');
    state.user = data.username;
    await initApp();
  } catch {
    showLogin();
  }
}

function showLogin() {
  document.getElementById('login-screen').classList.add('active');
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('app-screen').classList.add('hidden');
}

async function initApp() {
  document.getElementById('login-screen').classList.remove('active');
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');
  document.getElementById('username-display').textContent = state.user;

  await loadAllData();
  renderSidebar();
  renderCalendar();
}

// ── Boot ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

  // Login form
  document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const errEl = document.getElementById('login-error');
    errEl.classList.add('hidden');
    btn.querySelector('.btn-text').classList.add('hidden');
    btn.querySelector('.btn-spinner').classList.remove('hidden');
    btn.disabled = true;

    try {
      await api.post('/api/login', {
        username: document.getElementById('username-input').value,
        password: document.getElementById('password-input').value,
      });
      const me = await api.get('/api/me');
      state.user = me.username;
      await initApp();
    } catch (err) {
      errEl.textContent = err.message || 'Login failed';
      errEl.classList.remove('hidden');
    } finally {
      btn.querySelector('.btn-text').classList.remove('hidden');
      btn.querySelector('.btn-spinner').classList.add('hidden');
      btn.disabled = false;
    }
  });

  // Logout
  document.getElementById('logout-btn').addEventListener('click', async () => {
    await api.post('/api/logout', {});
    state.user = null;
    showLogin();
  });

  // Nav
  document.getElementById('nav-calendar').addEventListener('click', () => switchView('calendar'));
  document.getElementById('nav-contacts').addEventListener('click', () => switchView('contacts'));

  // Calendar nav
  document.getElementById('cal-prev').addEventListener('click', () => {
    if (state.calView === 'month') state.calDate.setMonth(state.calDate.getMonth() - 1);
    else state.calDate.setDate(state.calDate.getDate() - 7);
    state.calDate = new Date(state.calDate);
    renderCalendar();
  });
  document.getElementById('cal-next').addEventListener('click', () => {
    if (state.calView === 'month') state.calDate.setMonth(state.calDate.getMonth() + 1);
    else state.calDate.setDate(state.calDate.getDate() + 7);
    state.calDate = new Date(state.calDate);
    renderCalendar();
  });
  document.getElementById('cal-today-btn').addEventListener('click', () => {
    state.calDate = new Date();
    renderCalendar();
  });
  document.getElementById('view-month-btn').addEventListener('click', () => {
    state.calView = 'month';
    document.getElementById('view-month-btn').classList.add('active');
    document.getElementById('view-week-btn').classList.remove('active');
    renderCalendar();
  });
  document.getElementById('view-week-btn').addEventListener('click', () => {
    state.calView = 'week';
    document.getElementById('view-week-btn').classList.add('active');
    document.getElementById('view-month-btn').classList.remove('active');
    renderCalendar();
  });

  // Add buttons
  document.getElementById('add-event-btn').addEventListener('click', () => openNewEvent(new Date()));
  document.getElementById('add-contact-btn').addEventListener('click', openNewContact);
  document.getElementById('add-calendar-btn').addEventListener('click', () => openNewCollection('calendar'));
  document.getElementById('add-addressbook-btn').addEventListener('click', () => openNewCollection('addressbook'));

  // Forms
  document.getElementById('event-form').addEventListener('submit', saveEvent);
  document.getElementById('event-delete-btn').addEventListener('click', deleteEvent);
  document.getElementById('contact-form').addEventListener('submit', saveContact);
  document.getElementById('contact-delete-btn').addEventListener('click', deleteContact);
  document.getElementById('collection-form').addEventListener('submit', saveCollection);
  document.getElementById('col-delete-btn').addEventListener('click', deleteCollection);

  // Modal close buttons
  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => closeModal(btn.dataset.modal));
  });
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', e => {
      if (e.target === overlay) closeModal(overlay.id);
    });
  });

  // Color swatches
  document.querySelectorAll('.swatch').forEach(swatch => {
    swatch.addEventListener('click', () => {
      document.getElementById('col-color').value = swatch.dataset.color;
      document.querySelectorAll('.swatch').forEach(s => s.classList.remove('active'));
      swatch.classList.add('active');
    });
  });

  // Contacts search
  document.getElementById('contacts-search').addEventListener('input', renderContacts);

  // ESC to close modals
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => closeModal(m.id));
    }
  });

  // Boot
  checkAuth();
});
