import { F, T, R, I, C, shell, card, button, input, select, field, row, col, tabs, badge, sportBadge, avatar, progress, pageHeader, cardHeader, metricPill, metricsGrid, mapThumb, pagination, switchToggle, passwordInput, divider } from './ui.mjs'
import { streakCard } from './pages_activities.mjs'

const ghost = (icon) => button('', { variant: 'ghost', icon, size: 'sm' })
const ACCOUNT = [['My profile', 'user'], ['My goals', 'target'], ['Security', 'shield-check'], ['Integrations', 'plug'], ['Import', 'folder-input']]
const ADMIN = [['Users', 'users'], ['Identity providers', 'key-round'], ['Server settings', 'server-cog']]
function settingsNav(active) {
  const item = ([label, icon], on) => F(`Nav / ${label}${on ? ' (active)' : ''}`, { dir: 'h', gap: 10, pad: [8, 10], radius: 8, cross: 'center', sw: 'fill', fill: on ? '$secondary' : null },
    I(icon, on ? '$secondary-foreground' : '$muted-foreground', 16), T(label, { size: 14, weight: on ? 600 : 400, color: on ? '$secondary-foreground' : '$foreground' }))
  return card('Settings nav', { w: 256, sw: 'fixed', pad: 8, gap: 2 },
    F('Group', { dir: 'h', pad: [8, 8, 4, 8], sw: 'fill' }, T('Account', 'caption')), ACCOUNT.map((it, i) => item(it, active === it[0])),
    F('Group', { dir: 'h', pad: [12, 8, 4, 8], sw: 'fill' }, T('Administration', 'caption')), ADMIN.map((it) => item(it, active === it[0])))
}
const settingsShell = (name, active, content) => shell(`Settings – ${name}`, row('Layout', { gap: 12, sw: 'fill', cross: 'min' },
  F('Aside', { dir: 'v', gap: 12, w: 256 }, col('Header', { gap: 4, sw: 'fill' }, T('Settings', 'pageTitle'), T('Manage your instance and account', 'body', { sw: 'fill' })), settingsNav(active)),
  F('Content', { dir: 'v', gap: 12, sw: 'fill' }, content)))
const sub = (title, subtitle, actions) => pageHeader(title, { subtitle, actions })
const kv = (k, v) => col(k, { gap: 2, sw: 'fill' }, T(k, 'caption'), T(v, v === 'Not set' ? 'body' : 'bodyFg'))
const twoCol = (pairs) => col('Fields', { gap: 12, sw: 'fill' }, Array.from({ length: Math.ceil(pairs.length / 2) }, (_, i) => row(`Row ${i + 1}`, { gap: 24, sw: 'fill', cross: 'min' }, pairs.slice(i * 2, i * 2 + 2))))
const switchRow = (label, on, hint) => row(`Switch / ${label}`, { gap: 12, sw: 'fill', cross: 'min' }, switchToggle(on), col('Text', { gap: 2, sw: 'fill' }, T(label, 'bodyFg'), hint && T(hint, 'hint', { sw: 'fill' })))

// ---- My profile ----
export const profile = settingsShell('My profile', 'My profile', [
  sub('My profile', 'Manage your account details and privacy'),
  card('Profile info', {},
    row('Top', { gap: 16, sw: 'fill', cross: 'min' }, avatar('AR', 80),
      twoCol([kv('Name', 'Alex Rivera'), kv('Username', 'alexr'), kv('Email', 'alex@example.com'), kv('City', 'Zürich'), kv('Birth date', 'Mar 3, 1991'), kv('Gender', 'Not set'),
        kv('Units', 'Metric'), kv('Height', '180 cm'), kv('Preferred language', 'English'), kv('First day of week', 'Monday'), kv('Currency', 'Euro (€)'), kv('Access type', 'Administrator')])),
    row('Buttons', { gap: 8 }, button('Edit profile', { icon: 'pencil' }), button('Replace photo', { variant: 'outline', icon: 'upload' }), button('Remove photo', { variant: 'ghost', icon: 'trash-2' }))),
  card('Default gear', {}, T('Default gear', 'cardHeading'), T('Gear assigned automatically to new activities, by type', 'body'),
    ...[['Shoe activities', [['Run', 'Saucony Endorphin Speed 4'], ['Trail run', 'Not defined'], ['Walk', 'Hoka Clifton 9']]], ['Bike activities', [['Ride', 'Specialized Allez'], ['Gravel ride', 'Canyon Grizl CF SL'], ['Virtual ride', 'Not defined']]]].map(([g, items]) =>
      col(g, { gap: 8, sw: 'fill' }, T(g, 'itemTitle'), row('Selects', { gap: 24, sw: 'fill', cross: 'min' }, items.map(([l, v]) => field(l, select(v)))))),
    button('Save default gear')),
  card('Privacy', {}, T('Privacy', 'cardHeading'), T('Control what others can see on your shared activities', 'body'),
    row('Visibility', { gap: 24, sw: 'fill', cross: 'min' },
      field('Default activity visibility', select('Public'), { hint: 'Applied to new activities; existing ones keep their visibility' }),
      F('Bulk', { dir: 'v', gap: 6, sw: 'fill' }, field('Existing activities visibility', select('Followers'), { hint: 'Apply one visibility to every activity already in your account' }), button('Apply to existing activities', { variant: 'outline', size: 'sm' }))),
    T('Hide from shared activities', 'itemTitle'),
    row('Hide 1', { gap: 24, sw: 'fill' }, [['Start time', false], ['Location', true], ['Map', false], ['Heart rate', true]].map(([l, on]) => row(l, { gap: 8, sw: 'fill' }, switchToggle(on), T(l, 'bodyFg')))),
    row('Hide 2', { gap: 24, sw: 'fill' }, [['Power', false], ['Cadence', false], ['Elevation', false], ['Speed', false]].map(([l, on]) => row(l, { gap: 8, sw: 'fill' }, switchToggle(on), T(l, 'bodyFg')))),
    row('Hide 3', { gap: 24, sw: 'fill' }, [['Pace', false], ['Laps', false], ['Workout sets and steps', false], ['Gear', true]].map(([l, on]) => row(l, { gap: 8, sw: 'fill' }, switchToggle(on), T(l, 'bodyFg'))))),
  card('Your data', {}, T('Your data', 'cardHeading'), T('Export a copy of your data, or import a previous export', 'body'),
    row('Buttons', { gap: 8 }, button('Export data', { variant: 'outline', icon: 'download' }), button('Import data', { variant: 'outline', icon: 'upload' })),
    T('Exports don\'t include your password or security settings. Importing adds data to your account.', 'hint')),
])

// ---- My goals ----
const GOALS = [['footprints', 'Weekly running', 'Weekly · Run · Distance', '30 km', 0.72], ['bike', 'Monthly cycling', 'Monthly · Bike · Distance', '300 km', 1], ['activity', 'Weekly activities', 'Weekly · All · Number of activities', '3', 0.67], ['mountain-snow', 'Yearly elevation', 'Yearly · Walk · Elevation', '25,000 m', 0.48], ['flame', 'Daily calories', 'Daily · Cardio · Calories', '600 kcal', 0.31]]
export const goals = settingsShell('My goals', 'My goals', [
  sub('My goals', 'Set targets for your activities and track your progress', [button('Add goal', { icon: 'plus' })]),
  card('Goals list', { pad: 0, gap: 0 },
    F('Header', { dir: 'h', pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] }, T('There is a total of 5 goal(s):', 'hint', { sw: 'fill' }), button('Filters', { variant: 'outline', size: 'sm', icon: 'filter' })),
    GOALS.map(([icon, name, meta, target, pct], i) => F(`Goal / ${name}`, { dir: 'h', gap: 12, pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, i === GOALS.length - 1 ? 0 : 1, 0] },
      F('Icon', { dir: 'h', w: 40, h: 40, radius: 20, fill: '$muted', main: 'center', cross: 'center' }, I(icon, '$muted-foreground', 20)),
      col('Text', { gap: 2, sw: 'fill' }, T(name, { size: 15, weight: 600, color: '$foreground' }), T(meta, 'hint')),
      col('Target', { gap: 4, w: 200 }, row('Labels', { sw: 'fill', main: 'between' }, T(`Target ${target}`, 'hint'), T(`${Math.round(pct * 100)}%`, 'caption')), progress(pct, { w: 200, track: '$muted', color: pct >= 1 ? C.goal : C.brand })),
      row('Actions', { gap: 4 }, ghost('pencil'), ghost('trash-2'))))),
])

// ---- Security ----
export const security = settingsShell('Security', 'Security', [
  sub('Security', 'Manage your password, two-factor authentication and active sessions'),
  card('Change password', {}, cardHeader('Change password', { subtitle: 'Use a strong password you don\'t reuse elsewhere' }),
    row('Fields', { gap: 12, sw: 'fill', cross: 'min' }, field('Current password', passwordInput()), field('New password', passwordInput()), field('Confirm new password', passwordInput())),
    switchRow('Sign out of all other devices', true), button('Change password')),
  card('Two-factor', {}, cardHeader('Two-factor authentication', { subtitle: 'Add a one-time code from an authenticator app to your sign-ins' }),
    F('Alert', { dir: 'h', gap: 8, pad: [10, 12], radius: 8, sw: 'fill', fill: C.goal + '1A', stroke: C.goal + '66', cross: 'center' }, I('shield-check', C.goal, 16), T('Two-factor authentication is on. 8 backup codes remaining.', 'bodyFg', { sw: 'fill' })),
    row('Buttons', { gap: 8 }, button('Regenerate backup codes', { variant: 'outline' }), button('Disable two-factor', { variant: 'ghost' }))),
  card('Linked accounts', {}, cardHeader('Linked accounts', { subtitle: 'Sign in to your account with an external provider' }),
    row('Linked', { gap: 12, sw: 'fill', pad: [8, 12], radius: 8, stroke: '$border' }, I('key-round', '$muted-foreground', 18), col('Text', { gap: 2, sw: 'fill' }, T('Authentik', 'itemTitle'), T('Linked Mar 3, 2026', 'hint')), button('Unlink', { variant: 'outline', size: 'sm' })),
    T('Link an account', 'caption'), row('Available', { gap: 8 }, button('Pocket ID', { variant: 'outline', size: 'sm', icon: 'plus' }))),
  card('Sessions', {}, cardHeader('Active sessions', { subtitle: 'Devices currently signed in to your account', actions: [button('Sign out other devices', { variant: 'outline', size: 'sm' })] }),
    [['monitor', 'Firefox on Windows', '192.168.1.24 · Last active just now', true], ['smartphone', 'Endurain app on Android', '10.0.0.5 · Last active 2 hours ago'], ['laptop', 'Safari on macOS', '83.150.2.17 · Last active Oct 9, 2026']].map(([icon, n, m, cur]) =>
      row(`Session / ${n}`, { gap: 12, sw: 'fill', pad: [8, 0], stroke: '$border', sides: [0, 0, 1, 0] }, I(icon, '$muted-foreground', 20), col('Text', { gap: 2, sw: 'fill' }, row('Name', { gap: 8 }, T(n, 'itemTitle'), cur && badge('This device', 'secondary')), T(m, 'hint')), !cur && ghost('log-out')))),
  card('API keys', {}, cardHeader('API keys', { subtitle: 'Create keys to upload activities from scripts and third-party tools', actions: [button('Create API key', { size: 'sm', icon: 'plus' })] }),
    [['Home Assistant sync', 'Created Aug 2, 2026 · Last used yesterday · Never expires', 'Active'], ['Upload script', 'Created Jan 12, 2026 · Last used Sep 30, 2026 · Expires Jan 12, 2027', 'Active']].map(([n, m, s]) =>
      row(`Key / ${n}`, { gap: 12, sw: 'fill', pad: [8, 0], stroke: '$border', sides: [0, 0, 1, 0] }, col('Text', { gap: 2, sw: 'fill' }, row('Name', { gap: 8 }, T(n, 'itemTitle'), badge(s, 'goal')), T(m, 'hint')), button('Revoke', { variant: 'outline', size: 'sm' })))),
])

// ---- Integrations ----
const integration = (name, subtitle, iconFill, connected) => card(name, {},
  row('Head', { gap: 12, sw: 'fill' }, F('Logo', { dir: 'h', w: 40, h: 40, radius: 8, fill: iconFill, main: 'center', cross: 'center' }, I('plug', C.white, 20)),
    col('Text', { gap: 2, sw: 'fill' }, row('Title', { gap: 8 }, T(name, 'cardHeading'), connected && badge('Connected', 'goal')), T(subtitle, 'body')),
    connected ? button('Options', { variant: 'outline', iconRight: 'chevron-down' }) : button('Connect')))
export const integrations = settingsShell('Integrations', 'Integrations', [
  sub('Integrations', 'Connect Strava and Garmin Connect to import your activities and gear'),
  integration('Strava', 'Import your activities and gear from Strava', '#FC4C02', true),
  integration('Garmin Connect', 'Import your activities, gear and health data from Garmin Connect', '#000000', false),
])

// ---- Import ----
export const importPage = settingsShell('Import', 'Import', [
  sub('Import', 'Import activities and gear from files or a Strava bulk export'),
  card('Strava import', {}, row('Title', { gap: 8 }, T('Strava import', 'cardHeading'), badge('Beta', 'info')), T('Import from a Strava bulk export placed in the server\'s strava-import folder', 'body'),
    row('Buttons', { gap: 8 }, button('Import activities', { variant: 'outline', icon: 'download' }), button('Import bikes', { variant: 'outline', icon: 'bike' }), button('Import shoes', { variant: 'outline', icon: 'footprints' }))),
  card('Bulk import', {}, T('Bulk import', 'cardHeading'), T('Import activity files placed in the server\'s bulk-import folder', 'body'), button('Import activities', { icon: 'folder-input' })),
])

// ---- Users (admin) ----
const USERS = [['AR', 'Alex Rivera', '@alexr', [['Admin', 'info'], ['Active', 'goal']]], ['RM', 'Rita Meier', '@rita.m', [['Active', 'goal']]], ['BR', 'Bruno Ricci', '@bricci', [['Active', 'goal']]], ['CR', 'Carla Rinaldi', '@carlar', [['Pending approval', 'warning']]], ['JS', 'Jonas Steiner', '@jsteiner', [['Inactive', 'destructive']]]]
export const users = settingsShell('Users', 'Users', [
  sub('Users', 'Manage the accounts on this instance', [button('Add user', { icon: 'plus' })]),
  input('Search by username', { placeholder: true, icon: 'search' }),
  card('Users list', { pad: 0, gap: 0 },
    F('Header', { dir: 'h', pad: [12, 16], main: 'max', sw: 'fill', stroke: '$border', sides: [0, 0, 1, 0] }, button('Filters', { variant: 'outline', size: 'sm', icon: 'filter' })),
    USERS.map(([ini, n, u, bs], i) => F(`User / ${n}`, { dir: 'h', gap: 12, pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, i === USERS.length - 1 ? 0 : 1, 0] },
      avatar(ini, 40), col('Text', { gap: 2, sw: 'fill' }, T(n, { size: 15, weight: 600, color: '$foreground' }), row('Meta', { gap: 8 }, T(u, 'hint'), bs.map(([b, k]) => badge(b, k)))),
      row('Actions', { gap: 4 }, ghost('key-round'), ghost('pencil'), ghost('trash-2')))),
    F('Footer', { dir: 'h', pad: 12, sw: 'fill', stroke: '$border', sides: [1, 0, 0, 0] }, pagination(1, 1))),
])
export const userDetail = settingsShell('User detail', 'Users', [
  button('Back to users', { variant: 'ghost', size: 'sm', icon: 'arrow-left' }),
  card('User header', {}, row('Top', { gap: 16, sw: 'fill' }, avatar('CR', 64), col('Text', { gap: 4, sw: 'fill' }, T('Carla Rinaldi', 'cardHeading'), T('@carlar · carla@example.com', 'hint'), row('Badges', { gap: 8 }, badge('Pending approval', 'warning'), badge('Email verified', 'goal')))),
    row('Buttons', { gap: 8 }, button('Edit user', { variant: 'outline', icon: 'pencil' }), button('Upload photo', { variant: 'outline', icon: 'upload' }), button('Delete user', { variant: 'destructive', icon: 'trash-2' }))),
  card('Approval', {}, cardHeader('Pending approval', { subtitle: 'This sign-up is awaiting admin approval' }), row('Buttons', { gap: 8 }, button('Approve', { icon: 'check' }), button('Reject', { variant: 'outline', icon: 'x' }))),
  card('Profile', {}, T('Profile', 'cardHeading'), twoCol([kv('City', 'Milan'), kv('Birth date', 'Not set'), kv('Units', 'Metric'), kv('Preferred language', 'Italian'), kv('Access type', 'Regular user'), kv('Created', 'Oct 7, 2026')])),
  card('Security', {}, cardHeader('Security', { subtitle: 'Manage this account\'s sign-in', actions: [button('Reset password', { variant: 'outline', size: 'sm', icon: 'key-round' })] }),
    T('Identity providers', 'itemTitle'), T('No identity providers linked.', 'hint'), T('Sessions', 'itemTitle'), T('No active sessions.', 'hint')),
])

// ---- Identity providers (admin) ----
export const identityProviders = settingsShell('Identity providers', 'Identity providers', [
  sub('Identity providers', 'Configure SSO providers for single sign-on', [button('Add provider', { icon: 'plus' })]),
  card('Providers', { pad: 0, gap: 0 }, [['Authentik', 'https://auth.example.com/application/o/endurain/', true], ['Pocket ID', 'https://id.example.com', true], ['Keycloak (staging)', 'https://kc.staging.example.com/realms/main', false]].map(([n, u, on], i, a) =>
    F(`Provider / ${n}`, { dir: 'h', gap: 12, pad: [12, 16], cross: 'center', sw: 'fill', stroke: '$border', sides: [0, 0, i === a.length - 1 ? 0 : 1, 0] },
      F('Icon', { dir: 'h', w: 40, h: 40, radius: 20, fill: '$muted', main: 'center', cross: 'center' }, I('key-round', '$muted-foreground', 20)),
      col('Text', { gap: 2, sw: 'fill' }, row('Name', { gap: 8 }, T(n, { size: 15, weight: 600, color: '$foreground' }), badge(on ? 'Enabled' : 'Disabled', on ? 'goal' : 'outline')), T(u, 'hint')),
      row('Actions', { gap: 4 }, ghost('pencil'), ghost('trash-2'))))),
])

// ---- Server settings (admin) ----
const section = (title, ...kids) => card(title, {}, T(title, 'cardHeading'), kids)
export const server = settingsShell('Server settings', 'Server settings', [
  sub('Server settings', 'Configure instance-wide defaults and policies'),
  section('General', row('Fields', { gap: 12, sw: 'fill', cross: 'min' }, field('Default units', select('Metric')), field('Default currency', select('Euro (€)')), field('Records per page', select('25')))),
  section('Password policy', row('Fields', { gap: 12, sw: 'fill', cross: 'min' }, field('Policy', select('Strict (complexity required)')), field('Minimum length regular users', select('8')), field('Minimum length admin users', select('12')))),
  section('Registration', switchRow('Allow new user sign-ups', true), switchRow('Require admin approval for new sign-ups', true), switchRow('Require email verification for new sign-ups', false)),
  section('Authentication', switchRow('Enable SSO / single sign-on', true, 'Users can sign in with the identity providers configured below.'), switchRow('Allow local username and password login', true), switchRow('Auto-redirect to SSO', false)),
  section('Public sharing', switchRow('Enable public shareable links', false)),
  section('Maps', row('Fields', { gap: 12, sw: 'fill', cross: 'min' }, field('Tile server preset', select('OpenStreetMap')), field('Map background color', input('#E7EDE4', { icon: 'palette' }))),
    field('Tile server URL', input('https://tile.openstreetmap.org/{z}/{x}/{y}.png'), { hint: 'Must use https and include the z, x and y tile placeholders' }),
    field('Attribution', input('© OpenStreetMap contributors')), switchRow('Regenerate activity thumbnails when map settings change', false)),
  card('Login photo', {}, T('Login photo', 'cardHeading'), T('A custom image shown on the login screen', 'body'),
    row('Buttons', { gap: 8 }, button('Upload login photo', { variant: 'outline', icon: 'upload' }))),
  row('Save', { sw: 'fill', main: 'max' }, button('Save changes')),
])

// ---- Public user profile (/user/:id) ----
const miniCard = (name, run) => card(`Activity / ${name}`, {},
  row('Athlete', { gap: 12 }, avatar('RM', 48), col('Meta', { gap: 4 }, T('Rita Meier', 'itemTitle'), row('Badges', { gap: 8 }, run ? sportBadge('running', 'Running') : sportBadge('cycling', 'Cycling'), badge('Followers', 'secondary', { icon: 'users' })), T(run ? 'Sat, Oct 11, 2026 · 08:30 · Milan, Italy' : 'Wed, Oct 8, 2026 · 17:45 · Como, Italy', 'caption'))),
  T(name, 'cardHeading'),
  metricsGrid(run ? [['Distance', '21.1', 'km'], ['Time', '1:39:52'], ['Pace', '4:44', '/km', C.info]] : [['Distance', '48.6', 'km'], ['Time', '1:52:10'], ['Avg speed', '26.0', 'km/h', C.info]], 3),
  mapThumb({ w: 907, h: 240, route: run ? 'loop' : 'ride', water: run }))
export const userProfile = shell('User profile', row('Layout', { gap: 12, sw: 'fill', cross: 'min' },
  F('Left', { dir: 'v', gap: 12, w: 305 },
    card('Header', { cross: 'center' }, avatar('RM', 96), col('Name', { gap: 2, cross: 'center' }, T('Rita Meier', 'cardHeading'), T('@rita.m', 'caption')), row('City', { gap: 4 }, I('map-pin', '$muted-foreground', 14), T('Milan, Italy', 'hint'))),
    card('Actions', {}, button('Follow', { sw: 'fill', icon: 'user-plus' })),
    card('Stats', { gap: 8 }, ...[['Activities this month', '14'], ['Following', '38'], ['Followers', '52']].map(([l, v]) => row(l, { sw: 'fill' }, T(l, 'body', { sw: 'fill' }), T(v, 'itemTitle')))),
    card('Goals', {}, T('Goals', 'cardHeading'), ...[['Weekly running', 0.84, 'Distance: 25.2 / 30 km'], ['Monthly cycling', 0.41, 'Distance: 122 / 300 km']].map(([n, p, h]) =>
      col(n, { gap: 6, sw: 'fill' }, row('Head', { sw: 'fill' }, T(n, 'itemTitle', { sw: 'fill' }), T(`${Math.round(p * 100)}%`, 'caption')), progress(p, { track: '$muted' }), T(h, 'hint'))))),
  F('Right', { dir: 'v', gap: 12, sw: 'fill' },
    tabs(['Activities', 'Following', 'Followers'], 0, { icons: ['activity', 'users', 'users'] }),
    card('Week nav', { dir: 'h', gap: 8, cross: 'center' }, button('', { variant: 'outline', icon: 'chevron-left' }), T('Oct 6 – Oct 12, 2026', 'itemTitle', { sw: 'fill', align: 'center' }), button('This week', { variant: 'outline', size: 'sm' }), button('One year ago', { variant: 'outline', size: 'sm' }), button('', { variant: 'outline', icon: 'chevron-right' })),
    miniCard('Milano half marathon', true), miniCard('After-work ride to Como', false))))
