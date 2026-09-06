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

// ── State & i18n ─────────────────────────────────────────────
const i18n = {
  es: {
    // Nav & General
    calendar: 'Calendario',
    contacts: 'Contactos',
    calendars: 'Calendarios',
    addressbooks: 'Libretas',
    today: 'Hoy',
    month: 'Mes',
    week: 'Semana',
    tasks: 'Tareas',
    tasks_drawer_title: 'Tareas (VTODO)',
    quick_add: 'Cita Rápida',
    new_event: 'Nuevo Evento',
    new_contact: 'Nuevo Contacto',
    search_events: 'Buscar citas...',
    search_contacts: 'Buscar contactos...',
    add_task_placeholder: '+ Añadir tarea y pulsar Enter...',
    no_tasks: 'No hay tareas pendientes. ¡Añade una arriba!',
    no_contacts: 'No hay contactos aún. ¡Añade tu primer contacto!',
    no_contacts_found: 'No se encontraron contactos.',
    drag_task_hint: 'Arrastra al calendario para agendar',
    click_hide_cal: 'Clic para ocultar este calendario',
    click_show_cal: 'Clic para mostrar este calendario',
    edit: 'Editar',
    delete: 'Eliminar',
    save: 'Guardar',
    cancel: 'Cancelar',
    copy: 'Copiar',
    revoke: 'Revocar',
    more_events: '+{n} más',
    untitled: '(sin título)',
    confirm_delete_col: '¿Eliminar esta colección y todos sus elementos?',

    // Weekdays & Locale
    weekdays_short: ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'],
    locale: 'es-ES',

    // Login
    login_subtitle: 'Tu calendario y contactos personales',
    username: 'Usuario',
    clave: 'Contraseña',
    sign_in: 'Iniciar Sesión',
    username_placeholder: 'tu-usuario',

    // Modals
    modal_new_event: 'Nuevo Evento',
    modal_edit_event: 'Editar Evento',
    event_title: 'Título',
    event_start: 'Inicio',
    event_end: 'Fin',
    event_calendar: 'Calendario',
    event_location: 'Ubicación',
    event_reminder: 'Recordatorio',
    event_description: 'Descripción',
    save_event: 'Guardar Evento',

    modal_new_contact: 'Nuevo Contacto',
    modal_edit_contact: 'Editar Contacto',
    contact_firstname: 'Nombre',
    contact_lastname: 'Apellidos',
    contact_org: 'Empresa / Organización',
    contact_org_placeholder: 'ej: Google, Hospital, Autónomo...',
    contact_title: 'Cargo / Puesto',
    contact_title_placeholder: 'ej: Ingeniero, Diseñador...',
    contact_email: 'Correo electrónico',
    contact_phone: 'Teléfonos',
    contact_address: 'Dirección física / postal',
    contact_address_placeholder: 'Calle, número, ciudad, código postal',
    contact_bday: 'Cumpleaños',
    contact_notes: 'Notas / Apuntes',
    contact_notes_placeholder: 'Notas adicionales sobre este contacto...',
    contact_addressbook: 'Libreta de contactos',
    click_filter_ab: 'Clic para ver solo los contactos de esta libreta',
    click_show_all_ab: 'Filtro activo: clic para ver todas las libretas',
    save_contact: 'Guardar Contacto',
    add_phone: 'Añadir teléfono',
    tt_add_phone: 'Añadir otro número de teléfono a este contacto',
    delete_phone: 'Eliminar teléfono',
    create: 'Crear',
    new_calendar: 'Nuevo Calendario',
    create_new_calendar: 'Crear nuevo',
    create_new_calendar_option: 'Crear nuevo calendario...',
    cal_name_placeholder: 'Nombre del calendario...',
    tt_create_calendar: 'Crear un nuevo calendario',

    modal_new_cal: 'Nuevo Calendario',
    modal_new_ab: 'Nueva Libreta',
    modal_edit_collection: 'Editar Colección',
    collection_name: 'Nombre',
    collection_color: 'Color',
    data_sharing: 'Datos y Compartición',
    export_ics: '📥 Exportar .ics',
    import_ics: '📤 Importar .ics',
    public_link: '🔗 Enlace Público',

    quick_add_title: '⚡ Cita Rápida',
    quick_add_label: 'Descripción del evento (en español o inglés)',
    quick_add_placeholder: 'Ej: "Cena mañana 21:00 en Luigi" o "Meeting friday 10am"',
    quick_add_hint: 'Soporta fechas relativas (hoy, mañana, lunes...), horas (10:00, 3pm) y lugares (en / at).',
    when: 'Cuándo:',
    where: 'Dónde:',
    create_event: 'Crear Cita',

    shortcuts_title: 'Atajos de Teclado',
    sc_quick: 'Cita Rápida (Lenguaje Natural)',
    sc_search: 'Buscar Citas',
    sc_today: 'Ir al día de hoy',
    sc_month: 'Vista Mensual',
    sc_week: 'Vista Semanal',
    sc_prev: 'Período Anterior',
    sc_next: 'Período Siguiente',
    sc_new: 'Nuevo Evento',
    sc_close: 'Cerrar Ventanas',
    sc_guide: 'Guía de Atajos',

    connect_title: '📱 Conectar Dispositivos (CalDAV y CardDAV)',
    connect_apple_intro: 'Sincroniza calendario y contactos de forma nativa en iPhone, iPad y Mac:',
    connect_apple_step1: 'Ve a Ajustes > Calendario > Cuentas > Añadir cuenta > Otra.',
    connect_apple_step2: 'Selecciona Añadir cuenta CalDAV (o CardDAV para contactos).',
    connect_apple_step3: 'Introduce tu usuario, contraseña y la URL indicada abajo:',
    connect_android_intro: 'Sincroniza en Android mediante DAVx⁵ (código abierto):',
    connect_android_step1: 'Instala DAVx⁵ desde F-Droid o Google Play Store.',
    connect_android_step2: 'Pulsa + > Iniciar sesión con URL y nombre de usuario.',
    connect_android_step3: 'Introduce la URL base y tus credenciales de Kayendar:',
    connect_desktop_intro: 'Conecta con Mozilla Thunderbird, Apple Calendar o clientes de Linux/Windows:',
    caldav_url: 'URL CalDAV:',
    carddav_url: 'URL CardDAV (Contactos):',
    base_url: 'URL Base:',
    principal_url: 'URL CalDAV Principal:',

    // Reminders
    reminder_none: 'Ninguno',
    reminder_pt0s: 'A la hora del evento',
    reminder_pt5m: '5 minutos antes',
    reminder_pt15m: '15 minutos antes',
    reminder_pt30m: '30 minutos antes',
    reminder_pt1h: '1 hora antes',
    reminder_pt2h: '2 horas antes',
    reminder_p1d: '1 día antes',

    // Tooltips
    tt_shortcuts: 'Guía de atajos de teclado y ayuda (Atajo: ?)',
    tt_quick: 'Crear cita escribiendo en lenguaje natural (ej: "Cena mañana 21:00") (Atajo: Q)',
    tt_new_event: 'Crear evento con formulario completo (Atajo: C)',
    tt_search_events: 'Buscar citas por título, lugar o notas (Atajo: /)',
    tt_today: 'Ir al día de hoy (Atajo: T)',
    tt_month: 'Vista mensual (Atajo: M)',
    tt_week: 'Vista semanal con horas (Atajo: W)',
    tt_prev: 'Período anterior (Atajo: J o ←)',
    tt_next: 'Período siguiente (Atajo: K o →)',
    tt_tasks: 'Lista de tareas pendientes VTODO (arrástralas al calendario)',
    tt_calendar_nav: 'Ver tu calendario y eventos',
    tt_contacts_nav: 'Ver tus contactos y libreta',
    tt_add_calendar: 'Añadir nuevo calendario',
    tt_add_addressbook: 'Añadir libreta de contactos',
    tt_lang: 'Cambiar idioma / Switch language (ES / EN)',
    tt_week_start_mon: 'Primer día: Lunes (clic para cambiar a Domingo)',
    tt_week_start_sun: 'Primer día: Domingo (clic para cambiar a Lunes)',
    tt_connect: 'Sincronizar con iPhone o Android (CalDAV)',
    tt_logout: 'Cerrar sesión',
    tt_new_contact: 'Añadir nuevo contacto a la libreta',
    tt_close_tasks: 'Cerrar panel de tareas',
    tt_settings: 'Configuración y preferencias (Atajo: ,)',

    // Settings
    settings: 'Configuración',
    settings_title: 'Configuración y Preferencias',
    settings_general: 'General',
    settings_language: 'Idioma de la interfaz',
    settings_first_day: 'Primer día de la semana',
    monday: 'Lunes',
    sunday: 'Domingo',
    settings_about: 'Acerca de',
    settings_version: 'Versión instalada',
    settings_repo: 'Repositorio oficial',
    settings_sync_title: 'Sincronización de dispositivos',
    settings_sync_desc: 'Configura CalDAV y CardDAV en tu iPhone, Android o Thunderbird',
    settings_open_sync: 'Abrir asistente de sincronización...',
    sc_settings: 'Configuración',

    // Toasts
    task_deleted: 'Tarea eliminada',
    task_added: 'Tarea añadida',
    no_cal_for_task: 'No hay ningún calendario disponible para guardar la tarea',
    could_not_parse_event: 'No se pudo interpretar el evento',
    select_calendar: 'Por favor, selecciona un calendario',
    created_event: 'Cita creada: "{title}"',
    scheduled_on: 'Agendado "{title}" el {date}',
    moved_to: 'Movido "{title}" al {date}',
    rescheduled_to: 'Reprogramado para el {day} a las {time}',
    title_required: 'El título es obligatorio',
    name_required: 'El nombre es obligatorio',
    select_addressbook: 'Por favor, selecciona una libreta',
    event_saved: 'Evento guardado',
    event_deleted: 'Evento eliminado',
    contact_saved: 'Contacto guardado',
    contact_deleted: 'Contacto eliminado',
    collection_saved: 'Colección guardada',
    collection_created: 'Colección creada',
    collection_deleted: 'Colección eliminada',
    imported_items: 'Se importaron {n} elementos',
    share_link_generated: 'Enlace público generado',
    share_link_copied: 'Enlace copiado al portapapeles',
    share_link_revoked: 'Enlace público revocado',
    url_copied: 'URL copiada al portapapeles',
  },
  en: {
    // Nav & General
    calendar: 'Calendar',
    contacts: 'Contacts',
    calendars: 'Calendars',
    addressbooks: 'Address Books',
    today: 'Today',
    month: 'Month',
    week: 'Week',
    tasks: 'Tasks',
    tasks_drawer_title: 'Tasks (VTODO)',
    quick_add: 'Quick Add',
    new_event: 'New Event',
    new_contact: 'New Contact',
    search_events: 'Search events...',
    search_contacts: 'Search contacts...',
    add_task_placeholder: '+ Add a task and press Enter...',
    no_tasks: 'No tasks yet. Add a task above!',
    no_contacts: 'No contacts yet. Add your first contact!',
    no_contacts_found: 'No contacts found.',
    drag_task_hint: 'Drag to calendar to schedule',
    click_hide_cal: 'Click to hide this calendar',
    click_show_cal: 'Click to show this calendar',
    edit: 'Edit',
    delete: 'Delete',
    save: 'Save',
    cancel: 'Cancel',
    copy: 'Copy',
    revoke: 'Revoke',
    more_events: '+{n} more',
    untitled: '(untitled)',
    confirm_delete_col: 'Delete this collection and all its items?',

    // Weekdays & Locale
    weekdays_short: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
    locale: 'en-US',

    // Login
    login_subtitle: 'Your personal calendar & contacts',
    username: 'Username',
    clave: 'Password',
    sign_in: 'Sign In',
    username_placeholder: 'your-username',

    // Modals
    modal_new_event: 'New Event',
    modal_edit_event: 'Edit Event',
    event_title: 'Title',
    event_start: 'Start',
    event_end: 'End',
    event_calendar: 'Calendar',
    event_location: 'Location',
    event_reminder: 'Reminder',
    event_description: 'Description',
    save_event: 'Save Event',

    modal_new_contact: 'New Contact',
    modal_edit_contact: 'Edit Contact',
    contact_firstname: 'First name',
    contact_lastname: 'Last name',
    contact_org: 'Company / Organization',
    contact_org_placeholder: 'e.g.: Google, Hospital, Freelance...',
    contact_title: 'Job Title',
    contact_title_placeholder: 'e.g.: Engineer, Designer...',
    contact_email: 'Email',
    contact_phone: 'Phones',
    contact_address: 'Physical / Postal Address',
    contact_address_placeholder: 'Street, number, city, postal code',
    contact_bday: 'Birthday',
    contact_notes: 'Notes',
    contact_notes_placeholder: 'Additional notes about this contact...',
    contact_addressbook: 'Address Book',
    click_filter_ab: 'Click to view only contacts in this address book',
    click_show_all_ab: 'Filtered: click to view all address books',
    save_contact: 'Save Contact',
    add_phone: 'Add phone',
    tt_add_phone: 'Add another phone number to this contact',
    delete_phone: 'Delete phone',
    create: 'Create',
    new_calendar: 'New Calendar',
    create_new_calendar: 'Create new',
    create_new_calendar_option: 'Create new calendar...',
    cal_name_placeholder: 'Calendar name...',
    tt_create_calendar: 'Create a new calendar',

    modal_new_cal: 'New Calendar',
    modal_new_ab: 'New Address Book',
    modal_edit_collection: 'Edit Collection',
    collection_name: 'Name',
    collection_color: 'Color',
    data_sharing: 'Data & Sharing',
    export_ics: '📥 Export .ics',
    import_ics: '📤 Import .ics',
    public_link: '🔗 Public Link',

    quick_add_title: '⚡ Quick Add Event',
    quick_add_label: 'Event description (Spanish or English)',
    quick_add_placeholder: 'e.g. "Meeting friday 10am" or "Cena mañana 21:00 en Luigi"',
    quick_add_hint: 'Supports relative dates (today, tomorrow, monday...), times (10:00, 3pm), and locations (at / en).',
    when: 'When:',
    where: 'Where:',
    create_event: 'Create Event',

    shortcuts_title: 'Keyboard Shortcuts',
    sc_quick: 'Quick Add (Natural Language)',
    sc_search: 'Search Events',
    sc_today: 'Go to Today',
    sc_month: 'Month View',
    sc_week: 'Week View',
    sc_prev: 'Previous Period',
    sc_next: 'Next Period',
    sc_new: 'New Event',
    sc_close: 'Close Modals',
    sc_guide: 'Shortcuts Guide',

    connect_title: '📱 Connect Devices (CalDAV & CardDAV)',
    connect_apple_intro: 'Sync calendar & contacts with native iPhone, iPad, and Mac apps:',
    connect_apple_step1: 'Go to Settings > Calendar > Accounts > Add Account > Other.',
    connect_apple_step2: 'Select Add CalDAV Account (or CardDAV for contacts).',
    connect_apple_step3: 'Enter your Kayendar username, password, and URL below:',
    connect_android_intro: 'Sync seamlessly on Android using DAVx⁵ (open source):',
    connect_android_step1: 'Install DAVx⁵ from F-Droid or Google Play.',
    connect_android_step2: 'Tap + > Login with URL and user name.',
    connect_android_step3: 'Enter Base URL and your Kayendar username/password:',
    connect_desktop_intro: 'Connect with Mozilla Thunderbird, Apple Calendar, or Linux/Windows apps:',
    caldav_url: 'CalDAV URL:',
    carddav_url: 'CardDAV (Contacts) URL:',
    base_url: 'Base URL:',
    principal_url: 'Principal CalDAV URL:',

    // Reminders
    reminder_none: 'None',
    reminder_pt0s: 'At time of event',
    reminder_pt5m: '5 minutes before',
    reminder_pt15m: '15 minutes before',
    reminder_pt30m: '30 minutes before',
    reminder_pt1h: '1 hour before',
    reminder_pt2h: '2 hours before',
    reminder_p1d: '1 day before',

    // Tooltips
    tt_shortcuts: 'Keyboard shortcuts & help (Shortcut: ?)',
    tt_quick: 'Quick Add with natural language (e.g. "Meeting friday 10am") (Shortcut: Q)',
    tt_new_event: 'New event with full form (Shortcut: C)',
    tt_search_events: 'Search events by title, location or notes (Shortcut: /)',
    tt_today: 'Go to today (Shortcut: T)',
    tt_month: 'Month view (Shortcut: M)',
    tt_week: 'Week view with hourly slots (Shortcut: W)',
    tt_prev: 'Previous period (Shortcut: J or ←)',
    tt_next: 'Next period (Shortcut: K or →)',
    tt_tasks: 'Pending tasks list VTODO (drag to calendar to schedule)',
    tt_calendar_nav: 'View your calendar and events',
    tt_contacts_nav: 'View your contacts and address book',
    tt_add_calendar: 'Add new calendar',
    tt_add_addressbook: 'Add new address book',
    tt_lang: 'Switch language / Cambiar idioma (ES / EN)',
    tt_week_start_mon: 'First day: Monday (click for Sunday)',
    tt_week_start_sun: 'First day: Sunday (click for Monday)',
    tt_connect: 'Sync with iPhone or Android (CalDAV)',
    tt_logout: 'Log out',
    tt_new_contact: 'Add new contact to address book',
    tt_close_tasks: 'Close tasks drawer',
    tt_settings: 'Settings and preferences (Shortcut: ,)',

    // Settings
    settings: 'Settings',
    settings_title: 'Settings & Preferences',
    settings_general: 'General',
    settings_language: 'Interface Language',
    settings_first_day: 'First Day of Week',
    monday: 'Monday',
    sunday: 'Sunday',
    settings_about: 'About',
    settings_version: 'Installed Version',
    settings_repo: 'Official Repository',
    settings_sync_title: 'Device Synchronization',
    settings_sync_desc: 'Configure CalDAV and CardDAV on your iPhone, Android or Thunderbird',
    settings_open_sync: 'Open sync setup guide...',
    sc_settings: 'Settings',

    // Toasts
    task_deleted: 'Task deleted',
    task_added: 'Task added',
    no_cal_for_task: 'No calendar available to store task',
    could_not_parse_event: 'Could not parse event',
    select_calendar: 'Please select a calendar',
    created_event: 'Created event: "{title}"',
    scheduled_on: 'Scheduled "{title}" on {date}',
    moved_to: 'Moved "{title}" to {date}',
    rescheduled_to: 'Rescheduled to {day} at {time}',
    title_required: 'Title is required',
    name_required: 'Name is required',
    select_addressbook: 'Please select an address book',
    event_saved: 'Event saved',
    event_deleted: 'Event deleted',
    contact_saved: 'Contact saved',
    contact_deleted: 'Contact deleted',
    collection_saved: 'Collection updated',
    collection_created: 'Collection created',
    collection_deleted: 'Collection deleted',
    imported_items: 'Imported {n} items',
    share_link_generated: 'Public share link generated',
    share_link_copied: 'Share link copied to clipboard',
    share_link_revoked: 'Share link revoked',
    url_copied: 'URL copied to clipboard',
  }
};

function t(key, params = {}) {
  const currentLang = state.lang in i18n ? state.lang : 'es';
  let str = i18n[currentLang]?.[key] ?? i18n.es[key] ?? key;
  for (const [k, v] of Object.entries(params)) {
    str = str.replace(new RegExp(`\\{${k}\\}`, 'g'), v);
  }
  return str;
}

const state = {
  user: null,
  collections: [],
  events: {},   // slug -> [parsed event objects]
  contacts: {}, // slug -> [parsed contact objects]
  tasks: {},    // slug -> [parsed VTODO objects]
  visibleCalendars: {}, // slug -> boolean (default true)
  calendarSearch: '',
  calView: 'month',
  calDate: new Date(),
  activeView: 'calendar',
  showTasks: false,
  selectedAddressbook: null,
  lang: localStorage.getItem('kayendar_lang') || (navigator.language && navigator.language.startsWith('es') ? 'es' : 'en'),
  firstDayOfWeek: parseInt(localStorage.getItem('kayendar_first_day') ?? '1', 10), // 1 = Lunes/Monday (default), 0 = Domingo/Sunday
};

function updateWeekStartBtn() {
  const btn = document.getElementById('week-start-btn');
  if (btn) {
    if (state.firstDayOfWeek === 1) {
      btn.textContent = state.lang === 'en' ? '📅 Mon' : '📅 Lun';
      btn.setAttribute('data-tooltip', t('tt_week_start_mon'));
    } else {
      btn.textContent = state.lang === 'en' ? '📅 Sun' : '📅 Dom';
      btn.setAttribute('data-tooltip', t('tt_week_start_sun'));
    }
  }
  const settingFirstDay = document.getElementById('setting-first-day');
  if (settingFirstDay) settingFirstDay.value = String(state.firstDayOfWeek);
}

function setLanguage(lang) {
  if (lang !== 'es' && lang !== 'en') lang = 'es';
  state.lang = lang;
  localStorage.setItem('kayendar_lang', lang);
  document.documentElement.lang = lang;

  const langBtn = document.getElementById('lang-btn');
  if (langBtn) {
    langBtn.textContent = lang === 'es' ? '🌐 ES' : '🌐 EN';
    langBtn.setAttribute('data-tooltip', t('tt_lang'));
  }
  const settingLang = document.getElementById('setting-lang');
  if (settingLang) settingLang.value = lang;
  updateWeekStartBtn();

  // Translate all DOM elements with data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const k = el.getAttribute('data-i18n');
    if (k) el.textContent = t(k);
  });

  // Translate all input placeholders with data-i18n-placeholder
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    const k = el.getAttribute('data-i18n-placeholder');
    if (k) el.placeholder = t(k);
  });

  // Translate all elements with data-i18n-tooltip
  document.querySelectorAll('[data-i18n-tooltip]').forEach(el => {
    const k = el.getAttribute('data-i18n-tooltip');
    if (k) el.setAttribute('data-tooltip', t(k));
  });

  // Re-render views if initialized
  if (state.user) {
    renderSidebar();
    if (state.activeView === 'calendar') {
      renderCalendar();
    } else if (state.activeView === 'contacts') {
      renderContacts();
    }
    renderTasks();
  }
}

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

function parseTodos(content) {
  const lines = content.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  const todos = [];
  let cur = null;
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line === 'BEGIN:VTODO') { cur = { completed: false }; continue; }
    if (line === 'END:VTODO') { if (cur && (cur.title || cur.uid)) { todos.push(cur); } cur = null; continue; }
    if (!cur) continue;
    const colon = line.indexOf(':');
    if (colon < 0) continue;
    const key = line.slice(0, colon).split(';')[0].toUpperCase();
    const val = line.slice(colon + 1);
    if (key === 'SUMMARY') cur.title = val;
    if (key === 'STATUS') cur.completed = (val.toUpperCase() === 'COMPLETED');
    if (key === 'UID') cur.uid = val;
    if (key === 'DUE') cur.due = parseIcsDate(val);
    if (key === 'DESCRIPTION') cur.description = val;
  }
  return todos;
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

function buildTodoIcs(uid, title, completed = false) {
  const now = formatIcsDate(new Date()) + 'Z';
  const status = completed ? 'COMPLETED' : 'NEEDS-ACTION';
  const compLine = completed ? `COMPLETED:${now}` : '';
  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//Kayendar//EN',
    'BEGIN:VTODO',
    `UID:${uid}`,
    `DTSTAMP:${now}`,
    `SUMMARY:${title}`,
    `STATUS:${status}`,
    compLine,
    'END:VTODO',
    'END:VCALENDAR',
  ].filter(Boolean).join('\r\n') + '\r\n';
}

// ── vCard helpers ────────────────────────────────────────────
function parseVcf(content) {
  const contacts = [];
  const cards = content.split(/BEGIN:VCARD/i).slice(1);
  for (const card of cards) {
    const c = { phones: [] };
    for (const line of card.split(/\r?\n/)) {
      const colon = line.indexOf(':');
      if (colon < 0) continue;
      const fullKey = line.slice(0, colon).trim();
      const key = fullKey.split(';')[0].toUpperCase();
      const val = line.slice(colon + 1).trim();
      if (key === 'FN') c.fn = val;
      if (key === 'N') {
        const parts = val.split(';');
        c.lastName  = parts[0] || '';
        c.firstName = parts[1] || '';
      }
      if (key === 'EMAIL') c.email = val;
      if (key === 'TEL') {
        let type = 'CELL';
        const typeMatch = fullKey.match(/TYPE=([^;:]+)/i);
        if (typeMatch) {
          const tVal = typeMatch[1].toUpperCase();
          if (tVal.includes('WORK')) type = 'WORK';
          else if (tVal.includes('HOME')) type = 'HOME';
          else if (tVal.includes('CELL') || tVal.includes('MOBILE')) type = 'CELL';
          else if (tVal.includes('OTHER')) type = 'OTHER';
          else type = 'CELL';
        }
        if (val) {
          c.phones.push({ number: val, type });
        }
      }
      if (key === 'ADR') {
        // ADR components: po_box;extended;street;city;region;postal_code;country
        const parts = val.split(';').map(p => p.trim()).filter(Boolean);
        c.address = parts.join(', ');
      }
      if (key === 'ORG') {
        c.org = val.split(';')[0].trim();
      }
      if (key === 'TITLE') {
        c.title = val.trim();
      }
      if (key === 'NOTE') {
        c.notes = val.replace(/\\n/g, '\n').replace(/\\,/g, ',');
      }
      if (key === 'BDAY') {
        c.bday = val.trim();
      }
      if (key === 'UID') c.uid = val;
    }
    if (c.phones.length > 0) {
      c.phone = c.phones[0].number;
    } else {
      c.phone = '';
    }
    if (c.fn || c.firstName || c.lastName) contacts.push(c);
  }
  return contacts;
}

function buildVcf(uid, firstName, lastName, email, phones, address = '', org = '', title = '', notes = '', bday = '') {
  const telLines = [];
  if (Array.isArray(phones)) {
    phones.forEach(p => {
      const num = typeof p === 'string' ? p.trim() : (p.number || '').trim();
      const typ = (typeof p === 'object' && p.type) ? p.type.toUpperCase() : 'CELL';
      if (num) {
        telLines.push(`TEL;TYPE=${typ}:${num}`);
      }
    });
  } else if (phones && typeof phones === 'string' && phones.trim()) {
    telLines.push(`TEL;TYPE=CELL:${phones.trim()}`);
  }

  const lines = [
    'BEGIN:VCARD',
    'VERSION:3.0',
    `UID:${uid}`,
    `FN:${firstName} ${lastName}`.trim(),
    `N:${lastName};${firstName};;;`,
    email ? `EMAIL:${email}` : '',
    ...telLines,
    address ? `ADR;TYPE=HOME:;;${address.replace(/;/g, ' ')};;;;` : '',
    org ? `ORG:${org}` : '',
    title ? `TITLE:${title}` : '',
    notes ? `NOTE:${notes.replace(/\r?\n/g, '\\n').replace(/,/g, '\\,')}` : '',
    bday ? `BDAY:${bday}` : '',
    'END:VCARD',
  ];

  return lines.filter(Boolean).join('\r\n') + '\r\n';
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
  state.tasks = {};

  for (const col of state.collections) {
    try {
      const items = await api.get(`/api/collections/${col.slug}/items`);
      if (col.type === 'calendar') {
        state.events[col.slug] = [];
        state.tasks[col.slug] = [];
        for (const i of items) {
          const evs = parseIcs(i.content);
          evs.forEach(e => state.events[col.slug].push({ ...e, filename: i.filename, collectionSlug: col.slug, collectionColor: col.color }));
          const todos = parseTodos(i.content);
          todos.forEach(t => state.tasks[col.slug].push({ ...t, filename: i.filename, collectionSlug: col.slug, collectionColor: col.color }));
        }
      } else {
        state.contacts[col.slug] = items.flatMap(i => {
          const cs = parseVcf(i.content);
          return cs.map(c => ({ ...c, filename: i.filename, collectionSlug: col.slug }));
        });
      }
    } catch { /* skip */ }
  }
  updateTasksCount();
}

// ── Collections sidebar ──────────────────────────────────────
function renderSidebar() {
  const calList = document.getElementById('calendars-list');
  const abList  = document.getElementById('addressbooks-list');
  if (calList) calList.innerHTML = '';
  if (abList) abList.innerHTML  = '';

  // Contextual visibility: Only show calendars in calendar view, only addressbooks in contacts view
  const calSec = document.getElementById('sidebar-calendars-section');
  const abSec  = document.getElementById('sidebar-addressbooks-section');
  if (calSec && abSec) {
    if (state.activeView === 'calendar') {
      calSec.classList.remove('hidden');
      abSec.classList.add('hidden');
    } else if (state.activeView === 'contacts') {
      calSec.classList.add('hidden');
      abSec.classList.remove('hidden');
    }
  }

  for (const col of state.collections) {
    const isVisible = state.visibleCalendars[col.slug] !== false;
    const isAbActive = (col.type === 'addressbook' && state.selectedAddressbook === col.slug);
    const isAbFiltered = (col.type === 'addressbook' && state.selectedAddressbook !== null && !isAbActive);

    const el = document.createElement('div');
    if (col.type === 'calendar') {
      el.className = 'collection-item' + (isVisible ? ' active' : ' muted');
      el.title = isVisible ? t('click_hide_cal') : t('click_show_cal');
    } else {
      el.className = 'collection-item' + (isAbActive ? ' active' : (isAbFiltered ? ' muted' : ''));
      el.title = isAbActive ? t('click_show_all_ab') : t('click_filter_ab');
    }
    el.dataset.slug = col.slug;

    el.innerHTML = `
      <span class="collection-dot" style="background:${col.color}"></span>
      <span class="collection-name">${col.display_name}</span>
      <button class="collection-edit-btn" data-slug="${col.slug}" title="${t('edit')}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
      </button>`;

    el.addEventListener('click', (e) => {
      if (col.type === 'calendar') {
        state.visibleCalendars[col.slug] = !isVisible;
        renderSidebar();
        renderCalendar();
      } else if (col.type === 'addressbook') {
        state.selectedAddressbook = (state.selectedAddressbook === col.slug) ? null : col.slug;
        renderSidebar();
        renderContacts();
      }
    });

    el.querySelector('.collection-edit-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      openEditCollection(col);
    });

    if (col.type === 'calendar' && calList) calList.appendChild(el);
    else if (abList) abList.appendChild(el);
  }
}

// ── Tasks rendering ──────────────────────────────────────────
function allTasks() {
  return Object.values(state.tasks).flat();
}

function updateTasksCount() {
  const badge = document.getElementById('tasks-count');
  if (badge) {
    const uncompleted = allTasks().filter(t => !t.completed).length;
    badge.textContent = uncompleted;
  }
}

function renderTasks() {
  const list = document.getElementById('tasks-list');
  if (!list) return;
  list.innerHTML = '';
  const tasks = allTasks();
  updateTasksCount();

  if (!tasks.length) {
    const empty = document.createElement('div');
    empty.className = 'task-empty';
    empty.textContent = t('no_tasks');
    list.appendChild(empty);
    return;
  }

  // Sort: incomplete first, completed last
  tasks.sort((a, b) => (a.completed === b.completed ? 0 : a.completed ? 1 : -1));

  tasks.forEach(tItem => {
    const item = document.createElement('div');
    item.className = `task-item ${tItem.completed ? 'completed' : ''}`;
    item.setAttribute('draggable', 'true');
    item.title = t('drag_task_hint');
    item.addEventListener('dragstart', (e) => {
      e.dataTransfer.setData('application/json', JSON.stringify({
        type: 'task',
        uid: tItem.uid,
        title: tItem.title,
        collectionSlug: tItem.collectionSlug,
        filename: tItem.filename,
      }));
      e.dataTransfer.effectAllowed = 'copyMove';
      item.classList.add('dragging');
    });
    item.addEventListener('dragend', () => item.classList.remove('dragging'));

    const chk = document.createElement('input');
    chk.type = 'checkbox';
    chk.className = 'task-checkbox';
    chk.checked = !!tItem.completed;

    const titleSpan = document.createElement('span');
    titleSpan.className = `task-title ${tItem.completed ? 'completed' : ''}`;
    titleSpan.textContent = tItem.title || t('untitled');

    const delBtn = document.createElement('button');
    delBtn.className = 'task-delete-btn';
    delBtn.title = t('delete');
    delBtn.innerHTML = '&times;';

    chk.addEventListener('change', async () => {
      try {
        const newCompleted = chk.checked;
        const content = buildTodoIcs(tItem.uid, tItem.title, newCompleted);
        await api.put(`/api/collections/${tItem.collectionSlug}/items/${tItem.filename}`, { content });
        tItem.completed = newCompleted;
        renderTasks();
      } catch (err) {
        toast(err.message, 'error');
        chk.checked = !chk.checked;
      }
    });

    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try {
        await api.delete(`/api/collections/${tItem.collectionSlug}/items/${tItem.filename}`);
        toast(t('task_deleted'));
        await loadAllData();
        renderTasks();
      } catch (err) {
        toast(err.message, 'error');
      }
    });

    item.appendChild(chk);
    item.appendChild(titleSpan);
    item.appendChild(delBtn);
    list.appendChild(item);
  });
}

// ── Calendar rendering ───────────────────────────────────────
function allEvents() {
  let list = Object.entries(state.events)
    .filter(([slug]) => state.visibleCalendars[slug] !== false)
    .flatMap(([_, evs]) => evs);

  if (state.calendarSearch) {
    const q = state.calendarSearch.toLowerCase();
    list = list.filter(e =>
      (e.title && e.title.toLowerCase().includes(q)) ||
      (e.location && e.location.toLowerCase().includes(q)) ||
      (e.description && e.description.toLowerCase().includes(q))
    );
  }
  return list;
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
  const locale = i18n[state.lang]?.locale || 'es-ES';
  document.getElementById('cal-title').textContent =
    new Date(year, month, 1).toLocaleDateString(locale, { month: 'long', year: 'numeric' });

  let firstDay = new Date(year, month, 1).getDay();
  if (state.firstDayOfWeek === 1) {
    firstDay = (firstDay + 6) % 7;
  }
  const daysInMonth = new Date(year, month+1, 0).getDate();
  const today = new Date();

  const weekdays = document.createElement('div');
  weekdays.className = 'cal-weekdays';
  let baseWeekdays = i18n[state.lang]?.weekdays_short || ['Dom','Lun','Mar','Mié','Jue','Vie','Sáb'];
  if (state.firstDayOfWeek === 1) {
    baseWeekdays = [...baseWeekdays.slice(1), baseWeekdays[0]];
  }
  baseWeekdays.forEach(d => {
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
      evEl.textContent = ev.title || t('untitled');
      evEl.style.background = (ev.collectionColor || '#6366f1') + '33';
      evEl.style.color = ev.collectionColor || '#818cf8';
      evEl.title = ev.title;
      evEl.setAttribute('draggable', 'true');
      evEl.addEventListener('dragstart', (e) => {
        e.stopPropagation();
        e.dataTransfer.setData('application/json', JSON.stringify({
          type: 'event',
          uid: ev.uid,
          title: ev.title,
          collectionSlug: ev.collectionSlug,
          filename: ev.filename,
          start: ev.start,
          end: ev.end,
          description: ev.description,
          location: ev.location,
          alarm: ev.alarm
        }));
        evEl.classList.add('dragging');
      });
      evEl.addEventListener('dragend', () => evEl.classList.remove('dragging'));
      evEl.addEventListener('click', e => { e.stopPropagation(); openEditEvent(ev); });
      evContainer.appendChild(evEl);
    });
    if (dayEvents.length > 3) {
      const more = document.createElement('div');
      more.className = 'cal-more';
      more.textContent = t('more_events', { n: dayEvents.length - 3 });
      evContainer.appendChild(more);
    }
    cell.appendChild(evContainer);
  }

  // Drag and drop into cell
  cell.addEventListener('dragover', (e) => {
    e.preventDefault();
    cell.classList.add('drag-over');
  });
  cell.addEventListener('dragleave', () => {
    cell.classList.remove('drag-over');
  });
  cell.addEventListener('drop', async (e) => {
    e.preventDefault();
    cell.classList.remove('drag-over');
    try {
      const raw = e.dataTransfer.getData('application/json');
      if (!raw) return;
      const data = JSON.parse(raw);
      const loc = i18n[state.lang]?.locale || 'es-ES';
      if (data.type === 'task') {
        const cal = state.collections.find(c => c.type === 'calendar');
        if (!cal) return;
        const start = new Date(date); start.setHours(9, 0, 0, 0);
        const end = new Date(date); end.setHours(10, 0, 0, 0);
        const uid = generateUid();
        const content = buildIcs(uid, data.title, start, end);
        await api.put(`/api/collections/${cal.slug}/items/${uid}.ics`, { content });
        toast(t('scheduled_on', { title: data.title, date: date.toLocaleDateString(loc) }));
        await loadAllData();
        renderCalendar();
      } else if (data.type === 'event') {
        const origStart = new Date(data.start);
        const origEnd = new Date(data.end);
        const newStart = new Date(date);
        newStart.setHours(origStart.getHours(), origStart.getMinutes(), 0, 0);
        const dur = origEnd.getTime() - origStart.getTime();
        const newEnd = new Date(newStart.getTime() + (dur > 0 ? dur : 3600000));
        const content = buildIcs(data.uid, data.title, newStart, newEnd, data.description || '', data.location || '', data.alarm || '');
        await api.put(`/api/collections/${data.collectionSlug}/items/${data.filename}`, { content });
        toast(t('moved_to', { title: data.title, date: date.toLocaleDateString(loc) }));
        await loadAllData();
        renderCalendar();
      }
    } catch (err) {
      toast(err.message, 'error');
    }
  });

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
  let dow = date.getDay();
  if (state.firstDayOfWeek === 1) {
    dow = (dow + 6) % 7;
  }
  const weekStart = new Date(date); weekStart.setDate(date.getDate() - dow);
  const weekEnd = new Date(weekStart); weekEnd.setDate(weekStart.getDate() + 6);
  const locale = i18n[state.lang]?.locale || 'es-ES';

  document.getElementById('cal-title').textContent =
    `${weekStart.toLocaleDateString(locale, {month:'short', day:'numeric'})} – ${weekEnd.toLocaleDateString(locale, {month:'short', day:'numeric', year:'numeric'})}`;

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
    header.textContent = dayDate.toLocaleDateString(locale, {weekday:'short', day:'numeric'});
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
      evEl.textContent = ev.title || t('untitled');
      evEl.style.top = `${top}px`;
      evEl.style.height = `${height}px`;
      evEl.style.background = (ev.collectionColor || '#6366f1') + '44';
      evEl.style.color = ev.collectionColor || '#818cf8';
      evEl.style.borderLeft = `3px solid ${ev.collectionColor || '#6366f1'}`;
      evEl.setAttribute('draggable', 'true');
      evEl.addEventListener('dragstart', (e) => {
        e.stopPropagation();
        e.dataTransfer.setData('application/json', JSON.stringify({
          type: 'event',
          uid: ev.uid,
          title: ev.title,
          collectionSlug: ev.collectionSlug,
          filename: ev.filename,
          start: ev.start,
          end: ev.end,
          description: ev.description,
          location: ev.location,
          alarm: ev.alarm
        }));
        evEl.classList.add('dragging');
      });
      evEl.addEventListener('dragend', () => evEl.classList.remove('dragging'));
      evEl.addEventListener('click', () => openEditEvent(ev));
      eventsArea.appendChild(evEl);
    });

    if (isToday) {
      const now = new Date();
      const currentH = now.getHours() + now.getMinutes() / 60;
      const currentTop = currentH * 56;
      const timeLine = document.createElement('div');
      timeLine.className = 'current-time-line';
      timeLine.style.top = `${currentTop}px`;
      const timeDot = document.createElement('div');
      timeDot.className = 'time-dot';
      timeLine.appendChild(timeDot);
      eventsArea.appendChild(timeLine);
    }

    // Drag and drop into week day slot
    eventsArea.addEventListener('dragover', (e) => {
      e.preventDefault();
      eventsArea.classList.add('drag-over');
    });
    eventsArea.addEventListener('dragleave', () => {
      eventsArea.classList.remove('drag-over');
    });
    eventsArea.addEventListener('drop', async (e) => {
      e.preventDefault();
      eventsArea.classList.remove('drag-over');
      try {
        const raw = e.dataTransfer.getData('application/json');
        if (!raw) return;
        const data = JSON.parse(raw);
        const rect = eventsArea.getBoundingClientRect();
        const offsetY = Math.max(0, e.clientY - rect.top);
        const totalMinutes = Math.min(23 * 60 + 45, Math.floor(((offsetY / 56) * 60) / 15) * 15);
        const hour = Math.floor(totalMinutes / 60);
        const min = totalMinutes % 60;

        const newStart = new Date(dayDate);
        newStart.setHours(hour, min, 0, 0);

        if (data.type === 'task') {
          const cal = state.collections.find(c => c.type === 'calendar');
          if (!cal) return;
          const newEnd = new Date(newStart);
          newEnd.setHours(newStart.getHours() + 1);
          const uid = generateUid();
          const content = buildIcs(uid, data.title, newStart, newEnd);
          await api.put(`/api/collections/${cal.slug}/items/${uid}.ics`, { content });
          toast(t('scheduled_on', { title: data.title, date: `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}` }));
          await loadAllData();
          renderCalendar();
        } else if (data.type === 'event') {
          const origStart = new Date(data.start);
          const origEnd = new Date(data.end);
          const dur = origEnd.getTime() - origStart.getTime();
          const newEnd = new Date(newStart.getTime() + (dur > 0 ? dur : 3600000));
          const content = buildIcs(data.uid, data.title, newStart, newEnd, data.description || '', data.location || '', data.alarm || '');
          await api.put(`/api/collections/${data.collectionSlug}/items/${data.filename}`, { content });
          toast(t('rescheduled_to', { day: newStart.toLocaleDateString(locale, {weekday: 'short'}), time: `${String(hour).padStart(2,'0')}:${String(min).padStart(2,'0')}` }));
          await loadAllData();
          renderCalendar();
        }
      } catch (err) {
        toast(err.message, 'error');
      }
    });

    col.appendChild(eventsArea);
    col.addEventListener('click', (e) => {
      if (e.target === col || e.target === eventsArea) openNewEvent(dayDate);
    });
    weekGrid.appendChild(col);
  }

  grid.appendChild(weekGrid);
  setTimeout(() => {
    const currentHour = new Date().getHours();
    const targetScroll = Math.max(0, (currentHour - 1) * 56);
    weekGrid.scrollTo({ top: targetScroll, behavior: 'smooth' });
  }, 20);
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
  if (state.selectedAddressbook) {
    contacts = state.contacts[state.selectedAddressbook] || [];
  }

  if (search) {
    contacts = contacts.filter(c =>
      (c.fn || '').toLowerCase().includes(search) ||
      (c.firstName || '').toLowerCase().includes(search) ||
      (c.lastName || '').toLowerCase().includes(search) ||
      (c.email || '').toLowerCase().includes(search) ||
      (c.org || '').toLowerCase().includes(search) ||
      (c.title || '').toLowerCase().includes(search) ||
      (c.address || '').toLowerCase().includes(search) ||
      (c.notes || '').toLowerCase().includes(search) ||
      (c.phones || []).some(p => (p.number || '').toLowerCase().includes(search)) ||
      (c.phone || '').toLowerCase().includes(search)
    );
  }

  if (!contacts.length) {
    const empty = document.createElement('div');
    empty.className = 'contact-empty';
    empty.textContent = search ? t('no_contacts_found') : t('no_contacts');
    grid.appendChild(empty);
    return;
  }

  const typeIcons = { CELL: '📱', WORK: '💼', HOME: '🏠', OTHER: '📞' };

  contacts.forEach(c => {
    const name = c.fn || `${c.firstName || ''} ${c.lastName || ''}`.trim() || '?';
    const initials = name.split(' ').map(w => w[0]).join('').slice(0,2).toUpperCase();
    const colors = ['#6366f1','#ec4899','#f59e0b','#10b981','#3b82f6','#8b5cf6','#06b6d4'];
    const color = colors[(name.charCodeAt(0) || 0) % colors.length];

    let roleHtml = '';
    if (c.title || c.org) {
      const roleText = [c.title, c.org].filter(Boolean).join(' · ');
      roleHtml = `<div class="contact-role" title="${roleText}"><span class="detail-icon">💼</span><span>${roleText}</span></div>`;
    }

    let phonesHtml = '';
    if (c.phones && c.phones.length > 0) {
      phonesHtml = c.phones.map(p => `
        <div class="contact-detail-row contact-phone" title="${p.type}">
          <span class="detail-icon">${typeIcons[p.type] || '📞'}</span>
          <a href="tel:${encodeURIComponent(p.number)}" onclick="event.stopPropagation()">${p.number}</a>
        </div>
      `).join('');
    } else if (c.phone) {
      phonesHtml = `<div class="contact-detail-row contact-phone"><span class="detail-icon">📞</span><a href="tel:${encodeURIComponent(c.phone)}" onclick="event.stopPropagation()">${c.phone}</a></div>`;
    }

    const emailHtml = c.email ? `
      <div class="contact-detail-row contact-email" title="${c.email}">
        <span class="detail-icon">✉️</span>
        <a href="mailto:${c.email}" onclick="event.stopPropagation()">${c.email}</a>
      </div>` : '';

    const addressHtml = c.address ? `
      <div class="contact-detail-row contact-address" title="${c.address}">
        <span class="detail-icon">📍</span>
        <a href="https://maps.google.com/?q=${encodeURIComponent(c.address)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()">${c.address}</a>
      </div>` : '';

    const bdayHtml = c.bday ? `
      <div class="contact-detail-row contact-bday" title="${c.bday}">
        <span class="detail-icon">🎂</span>
        <span>${c.bday}</span>
      </div>` : '';

    const notesHtml = c.notes ? `
      <div class="contact-notes" title="${c.notes}">
        <span>${c.notes}</span>
      </div>` : '';

    const card = document.createElement('div');
    card.className = 'contact-card';
    card.innerHTML = `
      <div class="contact-avatar" style="background:${color}">${initials}</div>
      <div class="contact-name">${name}</div>
      ${roleHtml}
      ${emailHtml}
      ${phonesHtml}
      ${addressHtml}
      ${bdayHtml}
      ${notesHtml}
    `;
    card.addEventListener('click', () => openEditContact(c));
    grid.appendChild(card);
  });
}

// ── Natural Language Quick-Add Parser (ES & EN) ───────────────
function parseNaturalLanguageEvent(input) {
  if (!input || !input.trim()) return null;
  let text = input.trim();
  let location = '';
  const now = new Date();
  let targetDate = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 9, 0, 0);
  let timeSet = false;

  // 1. Location: "en [Location]" or "at [Location]"
  const locMatch = text.match(/(?:\s+(?:en|at)\s+)([^,.]+?)$/i);
  if (locMatch) {
    location = locMatch[1].trim();
    text = text.slice(0, locMatch.index).trim();
  }

  // 2. Time: e.g. "a las 19:30", "at 5pm", "17:00", "9am", "18h30", "18h"
  const timeRegex = /(?:\b(?:a\s+las?|at)\s+)?(\d{1,2})(?::(\d{2})|h(\d{2})?|\s*(am|pm))\b|(?:\b(?:a\s+las?|at)\s+)(\d{1,2})\b/i;
  const tMatch = text.match(timeRegex);
  if (tMatch) {
    let h = parseInt(tMatch[1] || tMatch[5], 10);
    let m = parseInt(tMatch[2] || tMatch[3] || 0, 10);
    const meridian = (tMatch[4] || '').toLowerCase();
    if (meridian === 'pm' && h < 12) h += 12;
    if (meridian === 'am' && h === 12) h = 0;
    if (h >= 0 && h <= 23 && m >= 0 && m <= 59) {
      targetDate.setHours(h, m, 0, 0);
      timeSet = true;
      text = text.replace(tMatch[0], ' ').trim();
    }
  }

  // 3. Date:
  // "pasado mañana" / "day after tomorrow"
  if (/\b(pasado\s+mañana|day\s+after\s+tomorrow)\b/i.test(text)) {
    targetDate.setDate(now.getDate() + 2);
    text = text.replace(/\b(pasado\s+mañana|day\s+after\s+tomorrow)\b/gi, ' ').trim();
  }
  // "mañana" / "tomorrow"
  else if (/\b(mañana|tomorrow)\b/i.test(text)) {
    targetDate.setDate(now.getDate() + 1);
    text = text.replace(/\b(mañana|tomorrow)\b/gi, ' ').trim();
  }
  // "hoy" / "today"
  else if (/\b(hoy|today)\b/i.test(text)) {
    targetDate.setDate(now.getDate());
    text = text.replace(/\b(hoy|today)\b/gi, ' ').trim();
  }
  // Weekday: "el lunes", "este viernes", "next monday", etc.
  else {
    const dayMap = {
      domingo: 0, sunday: 0,
      lunes: 1, monday: 1,
      martes: 2, tuesday: 2,
      miercoles: 3, miércoles: 3, wednesday: 3,
      jueves: 4, thursday: 4,
      viernes: 5, friday: 5,
      sabado: 6, sábado: 6, saturday: 6
    };
    const dayRegex = /\b(?:el\s+|este\s+|next\s+|on\s+)?(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/i;
    const dayMatch = text.match(dayRegex);
    if (dayMatch) {
      const dayName = dayMatch[1].toLowerCase().replace('é', 'e').replace('á', 'a');
      const targetDow = dayMap[dayName];
      if (targetDow !== undefined) {
        let diff = (targetDow - now.getDay() + 7) % 7;
        if (diff === 0 && !timeSet) diff = 7;
        targetDate.setDate(now.getDate() + diff);
        text = text.replace(dayMatch[0], ' ').trim();
      }
    }
  }

  const title = text.replace(/\s+/g, ' ').trim() || 'Quick Event';
  const end = new Date(targetDate);
  end.setHours(targetDate.getHours() + 1);

  return { title, start: targetDate, end, location };
}

function openQuickAdd() {
  const form = document.getElementById('quick-add-form');
  if (!form) return;
  form.reset();
  document.getElementById('quick-add-preview').classList.add('hidden');
  populateCalendarSelect('quick-add-calendar');
  openModal('quick-add-modal');
  setTimeout(() => document.getElementById('quick-add-input')?.focus(), 50);
}

function updateQuickAddPreview() {
  const input = document.getElementById('quick-add-input').value;
  const parsed = parseNaturalLanguageEvent(input);
  const prevBox = document.getElementById('quick-add-preview');
  if (!parsed || !input.trim()) {
    prevBox.classList.add('hidden');
    return;
  }
  prevBox.classList.remove('hidden');
  document.getElementById('qa-prev-title').textContent = parsed.title;
  document.getElementById('qa-prev-time').textContent = parsed.start.toLocaleString([], {
    weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });
  const locRow = document.getElementById('qa-prev-loc-row');
  if (parsed.location) {
    locRow.classList.remove('hidden');
    document.getElementById('qa-prev-loc').textContent = parsed.location;
  } else {
    locRow.classList.add('hidden');
  }
}

async function saveQuickAddEvent(e) {
  e.preventDefault();
  const input = document.getElementById('quick-add-input').value;
  const parsed = parseNaturalLanguageEvent(input);
  if (!parsed) { toast(t('could_not_parse_event'), 'error'); return; }

  const slug = document.getElementById('quick-add-calendar').value;
  if (!slug) { toast(t('select_calendar'), 'error'); return; }

  const uid = generateUid();
  const filename = uid + '.ics';
  const content = buildIcs(uid, parsed.title, parsed.start, parsed.end, '', parsed.location);

  try {
    await api.put(`/api/collections/${slug}/items/${filename}`, { content });
    toast(t('created_event', { title: parsed.title }));
    closeModal('quick-add-modal');
    await loadAllData();
    renderCalendar();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Connect Device Modal ──────────────────────────────────────
function openConnectModal() {
  const origin = window.location.origin;
  const user = state.user || 'username';

  const appleCal = document.getElementById('apple-caldav-url');
  const appleCard = document.getElementById('apple-carddav-url');
  const androidDav = document.getElementById('android-dav-url');
  const desktopDav = document.getElementById('desktop-dav-url');

  if (appleCal) appleCal.value = `${origin}/dav/`;
  if (appleCard) appleCard.value = `${origin}/dav/`;
  if (androidDav) androidDav.value = `${origin}/dav/`;
  if (desktopDav) desktopDav.value = `${origin}/dav/principals/${user}/`;

  openModal('connect-modal');
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
  document.getElementById('event-modal-title').textContent = t('modal_new_event');
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
  document.getElementById('event-modal-title').textContent = t('modal_edit_event');
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
  if (!sel) return;
  const cals = state.collections.filter(c => c.type === 'calendar');
  let html = cals.map(c =>
    `<option value="${c.slug}" ${c.slug === selectedSlug ? 'selected' : ''}>${c.display_name}</option>`
  ).join('');
  html += `<option value="__new_cal__">+ ${t('create_new_calendar_option')}</option>`;
  sel.innerHTML = html;
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

  if (!title) { toast(t('title_required'), 'error'); return; }
  if (!slug || slug === '__new_cal__') { toast(t('select_calendar'), 'error'); return; }

  if (!uid) uid = generateUid();
  if (!filename) filename = uid + '.ics';

  const content = buildIcs(uid, title, start, end, description, location, alarm);

  try {
    await api.put(`/api/collections/${slug}/items/${filename}`, { content });
    toast(t('event_saved'));
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
    toast(t('event_deleted'));
    closeModal('event-modal');
    await loadAllData();
    renderCalendar();
  } catch (err) {
    toast(err.message, 'error');
  }
}

// ── Contact modal ─────────────────────────────────────────────
function renderPhoneRow(container, phone = { number: '', type: 'CELL' }) {
  const row = document.createElement('div');
  row.className = 'phone-row';

  const select = document.createElement('select');
  select.className = 'phone-type-select';
  const types = [
    { val: 'CELL', label: '📱 Móvil' },
    { val: 'WORK', label: '💼 Trabajo' },
    { val: 'HOME', label: '🏠 Casa' },
    { val: 'OTHER', label: '📞 Otro' },
  ];
  if (state.lang === 'en') {
    types[0].label = '📱 Mobile';
    types[1].label = '💼 Work';
    types[2].label = '🏠 Home';
    types[3].label = '📞 Other';
  }
  select.innerHTML = types.map(tp =>
    `<option value="${tp.val}" ${tp.val === (phone.type || 'CELL') ? 'selected' : ''}>${tp.label}</option>`
  ).join('');

  const input = document.createElement('input');
  input.type = 'tel';
  input.className = 'phone-number-input';
  input.placeholder = '+34 600 000 000';
  input.value = phone.number || '';

  const removeBtn = document.createElement('button');
  removeBtn.type = 'button';
  removeBtn.className = 'icon-btn phone-remove-btn';
  removeBtn.title = t('delete_phone');
  removeBtn.innerHTML = '&times;';
  removeBtn.addEventListener('click', () => {
    const allRows = container.querySelectorAll('.phone-row');
    if (allRows.length > 1) {
      row.remove();
    } else {
      input.value = '';
    }
  });

  row.appendChild(select);
  row.appendChild(input);
  row.appendChild(removeBtn);
  container.appendChild(row);
  return input;
}

function openNewContact() {
  document.getElementById('contact-form').reset();
  document.getElementById('contact-modal-title').textContent = t('modal_new_contact');
  document.getElementById('contact-uid').value = '';
  document.getElementById('contact-filename').value = '';
  document.getElementById('contact-collection').value = '';
  const orgEl = document.getElementById('contact-org');
  if (orgEl) orgEl.value = '';
  const titleEl = document.getElementById('contact-title');
  if (titleEl) titleEl.value = '';
  const addrEl = document.getElementById('contact-address');
  if (addrEl) addrEl.value = '';
  const bdayEl = document.getElementById('contact-bday');
  if (bdayEl) bdayEl.value = '';
  const notesEl = document.getElementById('contact-notes');
  if (notesEl) notesEl.value = '';
  document.getElementById('contact-delete-btn').classList.add('hidden');
  const container = document.getElementById('contact-phones-container');
  if (container) {
    container.innerHTML = '';
    renderPhoneRow(container, { number: '', type: 'CELL' });
  }
  populateAddressbookSelect('contact-addressbook');
  openModal('contact-modal');
}

function openEditContact(c) {
  document.getElementById('contact-modal-title').textContent = t('modal_edit_contact');
  document.getElementById('contact-uid').value = c.uid || '';
  document.getElementById('contact-filename').value = c.filename || '';
  document.getElementById('contact-collection').value = c.collectionSlug || '';
  document.getElementById('contact-firstname').value = c.firstName || '';
  document.getElementById('contact-lastname').value  = c.lastName  || '';
  const orgEl = document.getElementById('contact-org');
  if (orgEl) orgEl.value = c.org || '';
  const titleEl = document.getElementById('contact-title');
  if (titleEl) titleEl.value = c.title || '';
  document.getElementById('contact-email').value     = c.email     || '';
  const addrEl = document.getElementById('contact-address');
  if (addrEl) addrEl.value = c.address || '';
  const bdayEl = document.getElementById('contact-bday');
  if (bdayEl) bdayEl.value = c.bday || '';
  const notesEl = document.getElementById('contact-notes');
  if (notesEl) notesEl.value = c.notes || '';

  const container = document.getElementById('contact-phones-container');
  if (container) {
    container.innerHTML = '';
    if (c.phones && c.phones.length > 0) {
      c.phones.forEach(p => renderPhoneRow(container, p));
    } else if (c.phone) {
      renderPhoneRow(container, { number: c.phone, type: 'CELL' });
    } else {
      renderPhoneRow(container, { number: '', type: 'CELL' });
    }
  }

  document.getElementById('contact-delete-btn').classList.remove('hidden');
  populateAddressbookSelect('contact-addressbook', c.collectionSlug);
  openModal('contact-modal');
}

async function saveContact(e) {
  e.preventDefault();
  const firstName = document.getElementById('contact-firstname').value.trim();
  const lastName  = document.getElementById('contact-lastname').value.trim();
  const org       = document.getElementById('contact-org')?.value.trim() || '';
  const title     = document.getElementById('contact-title')?.value.trim() || '';
  const email     = document.getElementById('contact-email').value.trim();
  const address   = document.getElementById('contact-address')?.value.trim() || '';
  const bday      = document.getElementById('contact-bday')?.value.trim() || '';
  const notes     = document.getElementById('contact-notes')?.value.trim() || '';
  const slug      = document.getElementById('contact-addressbook').value;
  let uid      = document.getElementById('contact-uid').value;
  let filename = document.getElementById('contact-filename').value;

  if (!lastName && !firstName) { toast(t('name_required'), 'error'); return; }
  if (!slug) { toast(t('select_addressbook'), 'error'); return; }

  const phones = [];
  const container = document.getElementById('contact-phones-container');
  if (container) {
    container.querySelectorAll('.phone-row').forEach(row => {
      const num = row.querySelector('.phone-number-input')?.value.trim();
      const typ = row.querySelector('.phone-type-select')?.value || 'CELL';
      if (num) {
        phones.push({ number: num, type: typ });
      }
    });
  }

  if (!uid) uid = generateUid();
  if (!filename) filename = uid + '.vcf';

  const content = buildVcf(uid, firstName, lastName, email, phones, address, org, title, notes, bday);

  try {
    await api.put(`/api/collections/${slug}/items/${filename}`, { content });
    toast(t('contact_saved'));
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
    toast(t('contact_deleted'));
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
  document.getElementById('collection-modal-title').textContent = type === 'calendar' ? t('modal_new_cal') : t('modal_new_ab');
  document.getElementById('col-type').value = type;
  document.getElementById('col-slug').value = '';
  document.getElementById('col-color').value = type === 'calendar' ? '#6366f1' : '#10b981';
  document.getElementById('col-delete-btn').classList.add('hidden');
  const tools = document.getElementById('col-tools-section');
  if (tools) tools.classList.add('hidden');
  const shareBox = document.getElementById('col-share-box');
  if (shareBox) shareBox.classList.add('hidden');
  openModal('collection-modal');
}

async function openEditCollection(col) {
  document.getElementById('collection-modal-title').textContent = t('modal_edit_collection');
  document.getElementById('col-name').value  = col.display_name;
  document.getElementById('col-color').value = col.color;
  document.getElementById('col-type').value  = col.type;
  document.getElementById('col-slug').value  = col.slug;
  document.getElementById('col-delete-btn').classList.remove('hidden');

  const toolsSection = document.getElementById('col-tools-section');
  const shareBox = document.getElementById('col-share-box');
  const shareUrlInput = document.getElementById('col-share-url');

  if (col.type === 'calendar' && toolsSection) {
    toolsSection.classList.remove('hidden');
    if (shareBox) shareBox.classList.add('hidden');
    if (shareUrlInput) shareUrlInput.value = '';

    try {
      const s = await api.get(`/api/collections/${col.slug}/share`);
      if (s.shared && s.url) {
        if (shareBox) shareBox.classList.remove('hidden');
        if (shareUrlInput) shareUrlInput.value = window.location.origin + s.url;
      }
    } catch { /* ignore */ }

    const exportBtn = document.getElementById('col-export-btn');
    if (exportBtn) {
      exportBtn.onclick = () => {
        window.location.href = `/api/collections/${col.slug}/export`;
      };
    }

    const importInput = document.getElementById('col-import-input');
    if (importInput) {
      importInput.value = '';
      importInput.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
          const text = await file.text();
          const res = await fetch(`/api/collections/${col.slug}/import`, {
            method: 'POST',
            headers: { 'Content-Type': 'text/calendar; charset=utf-8' },
            body: text,
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data?.error || 'Import failed');
          toast(t('imported_items', { n: data.imported || 0 }));
          closeModal('collection-modal');
          await loadAllData();
          renderCalendar();
          if (state.showTasks) renderTasks();
        } catch (err) {
          toast(err.message, 'error');
        }
      };
    }

    const shareBtn = document.getElementById('col-share-btn');
    if (shareBtn) {
      shareBtn.onclick = async () => {
        try {
          const s = await api.post(`/api/collections/${col.slug}/share`, {});
          if (shareBox) shareBox.classList.remove('hidden');
          if (shareUrlInput) shareUrlInput.value = window.location.origin + s.url;
          toast(t('share_link_generated'));
        } catch (err) {
          toast(err.message, 'error');
        }
      };
    }

    const copyBtn = document.getElementById('copy-share-btn');
    if (copyBtn) {
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(shareUrlInput.value);
          toast(t('share_link_copied'));
        } catch {
          shareUrlInput.select();
          document.execCommand('copy');
          toast(t('share_link_copied'));
        }
      };
    }

    const revokeBtn = document.getElementById('revoke-share-btn');
    if (revokeBtn) {
      revokeBtn.onclick = async () => {
        try {
          await api.delete(`/api/collections/${col.slug}/share`);
          if (shareBox) shareBox.classList.add('hidden');
          if (shareUrlInput) shareUrlInput.value = '';
          toast(t('share_link_revoked'));
        } catch (err) {
          toast(err.message, 'error');
        }
      };
    }
  } else {
    if (toolsSection) toolsSection.classList.add('hidden');
    if (shareBox) shareBox.classList.add('hidden');
  }

  openModal('collection-modal');
}

async function saveCollection(e) {
  e.preventDefault();
  const name  = document.getElementById('col-name').value.trim();
  const color = document.getElementById('col-color').value;
  const type  = document.getElementById('col-type').value;
  const slug  = document.getElementById('col-slug').value;

  if (!name) { toast(t('name_required'), 'error'); return; }

  try {
    if (slug) {
      await api.patch(`/api/collections/${slug}`, { display_name: name, color });
      toast(t('collection_saved'));
    } else {
      await api.post('/api/collections', { display_name: name, color, type });
      toast(t('collection_created'));
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
  if (!confirm(t('confirm_delete_col'))) return;
  try {
    await api.delete(`/api/collections/${slug}`);
    toast(t('collection_deleted'));
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
  renderSidebar();
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
  renderTasks();
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
  function goToToday() {
    state.calDate = new Date();
    renderCalendar();

    setTimeout(() => {
      if (state.calView === 'month') {
        const todayCell = document.querySelector('.cal-day--today');
        if (todayCell) {
          todayCell.classList.add('pulse-today');
          todayCell.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          setTimeout(() => todayCell.classList.remove('pulse-today'), 1500);
        }
      } else if (state.calView === 'week') {
        const todayHeader = document.querySelector('.week-day-header.today');
        if (todayHeader) {
          todayHeader.classList.add('pulse-today');
          setTimeout(() => todayHeader.classList.remove('pulse-today'), 1500);
        }
        const weekGrid = document.querySelector('.week-grid');
        if (weekGrid) {
          const currentHour = new Date().getHours();
          const targetScroll = Math.max(0, (currentHour - 1) * 56);
          weekGrid.scrollTo({ top: targetScroll, behavior: 'smooth' });
        }
      }
    }, 20);
  }

  document.getElementById('cal-today-btn').addEventListener('click', goToToday);
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

  // Tasks Drawer
  const toggleBtn = document.getElementById('toggle-tasks-btn');
  const closeBtn  = document.getElementById('close-tasks-btn');
  const drawer    = document.getElementById('tasks-drawer');

  function toggleTasksDrawer(show) {
    if (drawer) {
      if (show === undefined) show = drawer.classList.contains('hidden');
      state.showTasks = show;
      if (show) {
        drawer.classList.remove('hidden');
        renderTasks();
      } else {
        drawer.classList.add('hidden');
      }
    }
  }

  if (toggleBtn) toggleBtn.addEventListener('click', () => toggleTasksDrawer());
  if (closeBtn)  closeBtn.addEventListener('click', () => toggleTasksDrawer(false));

  const taskForm = document.getElementById('new-task-form');
  if (taskForm) {
    taskForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = document.getElementById('new-task-input');
      const title = input.value.trim();
      if (!title) return;

      const cal = state.collections.find(c => c.type === 'calendar');
      if (!cal) {
        toast(t('no_cal_for_task'), 'error');
        return;
      }

      const uid = generateUid();
      const filename = `${uid}.ics`;
      const content = buildTodoIcs(uid, title, false);

      try {
        await api.put(`/api/collections/${cal.slug}/items/${filename}`, { content });
        input.value = '';
        await loadAllData();
        renderTasks();
        toast(t('task_added'));
      } catch (err) {
        toast(err.message, 'error');
      }
    });
  }

  // Shortcuts modal
  const shortcutsBtn = document.getElementById('shortcuts-btn');
  if (shortcutsBtn) {
    shortcutsBtn.addEventListener('click', () => openModal('shortcuts-modal'));
  }

  // Forms
  document.getElementById('event-form').addEventListener('submit', saveEvent);
  document.getElementById('event-delete-btn').addEventListener('click', deleteEvent);
  document.getElementById('contact-form').addEventListener('submit', saveContact);
  document.getElementById('contact-delete-btn').addEventListener('click', deleteContact);
  document.getElementById('collection-form').addEventListener('submit', saveCollection);
  document.getElementById('col-delete-btn').addEventListener('click', deleteCollection);

  // Add phone button in contact modal
  const addPhoneBtn = document.getElementById('contact-add-phone-btn');
  if (addPhoneBtn) {
    addPhoneBtn.addEventListener('click', () => {
      const container = document.getElementById('contact-phones-container');
      if (container) {
        const input = renderPhoneRow(container, { number: '', type: 'CELL' });
        if (input) input.focus();
      }
    });
  }

  // Inline calendar creation in event modal
  const eventCalSelect = document.getElementById('event-calendar');
  const inlineCalBox = document.getElementById('event-inline-cal-box');
  const inlineCalToggleBtn = document.getElementById('event-new-cal-toggle-btn');
  const inlineCalSaveBtn = document.getElementById('inline-cal-save-btn');
  const inlineCalCancelBtn = document.getElementById('inline-cal-cancel-btn');
  const inlineCalName = document.getElementById('inline-cal-name');
  const inlineCalColor = document.getElementById('inline-cal-color');

  let lastSelectedCalSlug = '';

  if (eventCalSelect) {
    eventCalSelect.addEventListener('focus', () => {
      if (eventCalSelect.value !== '__new_cal__') {
        lastSelectedCalSlug = eventCalSelect.value;
      }
    });
    eventCalSelect.addEventListener('change', () => {
      if (eventCalSelect.value === '__new_cal__') {
        if (inlineCalBox) {
          inlineCalBox.classList.remove('hidden');
          if (inlineCalName) inlineCalName.focus();
        }
      } else {
        lastSelectedCalSlug = eventCalSelect.value;
      }
    });
  }

  if (inlineCalToggleBtn) {
    inlineCalToggleBtn.addEventListener('click', () => {
      if (inlineCalBox) {
        const isHidden = inlineCalBox.classList.toggle('hidden');
        if (!isHidden && inlineCalName) {
          inlineCalName.focus();
        }
      }
    });
  }

  if (inlineCalCancelBtn) {
    inlineCalCancelBtn.addEventListener('click', () => {
      if (inlineCalBox) inlineCalBox.classList.add('hidden');
      if (eventCalSelect && lastSelectedCalSlug) {
        eventCalSelect.value = lastSelectedCalSlug;
      } else if (eventCalSelect) {
        const firstCal = state.collections.find(c => c.type === 'calendar');
        if (firstCal) eventCalSelect.value = firstCal.slug;
      }
    });
  }

  if (inlineCalSaveBtn) {
    inlineCalSaveBtn.addEventListener('click', async () => {
      const name = inlineCalName?.value.trim();
      const color = inlineCalColor?.value || '#6366f1';
      if (!name) {
        toast(t('name_required'), 'error');
        if (inlineCalName) inlineCalName.focus();
        return;
      }
      try {
        const created = await api.post('/api/collections', { display_name: name, color, type: 'calendar' });
        toast(t('collection_created'));
        if (inlineCalName) inlineCalName.value = '';
        if (inlineCalBox) inlineCalBox.classList.add('hidden');
        await loadAllData();
        renderSidebar();
        renderCalendar();
        populateCalendarSelect('event-calendar', created.slug);
        lastSelectedCalSlug = created.slug;
      } catch (err) {
        toast(err.message, 'error');
      }
    });
  }

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

  // Calendar search
  const calSearch = document.getElementById('calendar-search');
  if (calSearch) {
    calSearch.addEventListener('input', (e) => {
      state.calendarSearch = e.target.value.trim();
      renderCalendar();
    });
  }

  // Quick Add (NLP)
  const quickAddBtn = document.getElementById('quick-add-btn');
  if (quickAddBtn) quickAddBtn.addEventListener('click', openQuickAdd);

  const quickAddInput = document.getElementById('quick-add-input');
  if (quickAddInput) quickAddInput.addEventListener('input', updateQuickAddPreview);

  const quickAddForm = document.getElementById('quick-add-form');
  if (quickAddForm) quickAddForm.addEventListener('submit', saveQuickAddEvent);

  // Connect Device modal & tabs
  const connectBtn = document.getElementById('connect-device-btn');
  if (connectBtn) connectBtn.addEventListener('click', openConnectModal);

  document.querySelectorAll('.connect-tab-btn').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.connect-tab-btn').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.connect-pane').forEach(p => p.classList.add('hidden'));
      tab.classList.add('active');
      const targetPane = document.getElementById(tab.dataset.tab);
      if (targetPane) targetPane.classList.remove('hidden');
    });
  });

  document.querySelectorAll('.copy-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const input = document.getElementById(btn.dataset.target);
      if (input) {
        try {
          await navigator.clipboard.writeText(input.value);
        } catch {
          input.select();
          document.execCommand('copy');
        }
        toast(t('url_copied'));
      }
    });
  });

  // Week start toggle button (Monday / Sunday)
  const weekStartBtn = document.getElementById('week-start-btn');
  if (weekStartBtn) {
    weekStartBtn.addEventListener('click', () => {
      state.firstDayOfWeek = state.firstDayOfWeek === 1 ? 0 : 1;
      localStorage.setItem('kayendar_first_day', String(state.firstDayOfWeek));
      updateWeekStartBtn();
      renderCalendar();
    });
  }

  // Language toggle button
  const langBtn = document.getElementById('lang-btn');
  if (langBtn) {
    langBtn.addEventListener('click', () => {
      setLanguage(state.lang === 'es' ? 'en' : 'es');
    });
  }

  // Settings modal handlers
  function openSettingsModal() {
    const langSel = document.getElementById('setting-lang');
    if (langSel) langSel.value = state.lang;
    const firstDaySel = document.getElementById('setting-first-day');
    if (firstDaySel) firstDaySel.value = String(state.firstDayOfWeek);
    openModal('settings-modal');
  }

  const settingsBtn = document.getElementById('settings-btn');
  if (settingsBtn) settingsBtn.addEventListener('click', openSettingsModal);
  const sidebarSettingsBtn = document.getElementById('sidebar-settings-btn');
  if (sidebarSettingsBtn) sidebarSettingsBtn.addEventListener('click', openSettingsModal);

  const settingLang = document.getElementById('setting-lang');
  if (settingLang) {
    settingLang.addEventListener('change', (e) => {
      setLanguage(e.target.value);
    });
  }

  const settingFirstDay = document.getElementById('setting-first-day');
  if (settingFirstDay) {
    settingFirstDay.addEventListener('change', (e) => {
      state.firstDayOfWeek = parseInt(e.target.value, 10);
      localStorage.setItem('kayendar_first_day', String(state.firstDayOfWeek));
      updateWeekStartBtn();
      renderCalendar();
    });
  }

  const settingsSyncBtn = document.getElementById('settings-open-sync-btn');
  if (settingsSyncBtn) {
    settingsSyncBtn.addEventListener('click', () => {
      closeModal('settings-modal');
      openConnectModal();
    });
  }

  // Contacts search
  document.getElementById('contacts-search').addEventListener('input', renderContacts);

  // Keyboard navigation & shortcuts
  document.addEventListener('keydown', e => {
    const tag = e.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target.isContentEditable) {
      if (e.key === 'Escape') {
        e.target.blur();
        document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => closeModal(m.id));
      }
      return;
    }

    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay:not(.hidden)').forEach(m => closeModal(m.id));
      return;
    }

    const modalOpen = document.querySelector('.modal-overlay:not(.hidden)');
    if (modalOpen) return;

    const key = e.key.toLowerCase();
    if (key === ',') {
      e.preventDefault();
      openSettingsModal();
      return;
    }

    if (state.activeView !== 'calendar') return;

    if (key === 'q') {
      e.preventDefault();
      openQuickAdd();
    } else if (key === '/') {
      e.preventDefault();
      if (calSearch) calSearch.focus();
    } else if (key === 't') {
      e.preventDefault();
      goToToday();
    } else if (key === 'm') {
      e.preventDefault();
      state.calView = 'month';
      document.getElementById('view-month-btn').classList.add('active');
      document.getElementById('view-week-btn').classList.remove('active');
      renderCalendar();
    } else if (key === 'w') {
      e.preventDefault();
      state.calView = 'week';
      document.getElementById('view-week-btn').classList.add('active');
      document.getElementById('view-month-btn').classList.remove('active');
      renderCalendar();
    } else if (key === 'j' || e.key === 'ArrowLeft') {
      e.preventDefault();
      if (state.calView === 'month') state.calDate.setMonth(state.calDate.getMonth() - 1);
      else state.calDate.setDate(state.calDate.getDate() - 7);
      state.calDate = new Date(state.calDate);
      renderCalendar();
    } else if (key === 'k' || e.key === 'ArrowRight') {
      e.preventDefault();
      if (state.calView === 'month') state.calDate.setMonth(state.calDate.getMonth() + 1);
      else state.calDate.setDate(state.calDate.getDate() + 7);
      state.calDate = new Date(state.calDate);
      renderCalendar();
    } else if (key === 'c') {
      e.preventDefault();
      openNewEvent(new Date());
    } else if (key === '?') {
      e.preventDefault();
      openModal('shortcuts-modal');
    }
  });

  // PWA Service Worker Registration
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }

  // Initialize Language & Boot
  setLanguage(state.lang);
  checkAuth();
});
