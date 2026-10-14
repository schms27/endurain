import { F, T, R, I, INST, IMG, C, bare, shell, card, button, input, passwordInput, field, row, col } from './ui.mjs'

const gradient = {
  type: 'GRADIENT_LINEAR',
  gradientHandlePositions: [{ x: 0.5, y: 0 }, { x: 0.5, y: 1 }, { x: 1, y: 0 }],
  gradientStops: [
    { position: 0, color: { r: 0, g: 0, b: 0, a: 0.4 } },
    { position: 0.5, color: { r: 0, g: 0, b: 0, a: 0 } },
    { position: 1, color: { r: 0, g: 0, b: 0, a: 0.75 } },
  ],
}

/** AuthScreenLayout: photo with taglines on the left, form on the right. */
function authLayout(name, form, h = 640) {
  return bare(name, F('Auth card', { dir: 'h', gap: 12, pad: 12, w: 1256, fill: '$card', stroke: '$border', radius: 12, clip: true },
    IMG('login', { w: 616, h, radius: 8, clip: true, sw: 'fill', sh: 'fixed' },
      R('Scrim', { x: 0, y: 0, w: 616, h, fill: gradient, absolute: true }),
      F('Taglines', { dir: 'v', x: 24, y: h - 88, absolute: true }, T('Track every move', { size: 22, weight: 600, color: C.white }), T('Own every moment', { size: 22, weight: 600, color: C.white }))),
    F('Form column', { dir: 'v', sw: 'fill', h, sh: 'fixed', main: 'center', cross: 'center', pad: [24, 32] }, form),
  ), { h: Math.max(900, h + 200) })
}
const formCol = (...kids) => F('Form', { dir: 'v', w: 384, cross: 'center' }, kids)
const logo = () => INST('Logo', { w: 40, h: 40 })

export const login = authLayout('Login', formCol(
  logo(), F('gap', { h: 12, w: 1 }),
  T('Endurain', 'pageTitle', { align: 'center' }),
  F('gap', { h: 8, w: 1 }),
  T('Sign-in below', 'body', { align: 'center' }),
  F('Fields', { dir: 'v', gap: 12, sw: 'fill', pad: [20, 0, 0, 0], cross: 'center' },
    field('Username', input('Username', { placeholder: true })),
    field('Password', passwordInput()),
    button('Sign in', { sw: 'fill' }),
    T('Forgot password?', 'meta'),
    T('Create an account', 'meta'),
  ),
  F('SSO', { dir: 'v', gap: 12, sw: 'fill', pad: [20, 0, 0, 0] },
    row('Divider', { gap: 12, sw: 'fill' }, R('Line', { h: 1, sw: 'fill', fill: '$border' }), T('Single sign-on', 'caption'), R('Line', { h: 1, sw: 'fill', fill: '$border' })),
    button('Continue with Authentik', { variant: 'outline', sw: 'fill', icon: 'key-round' }),
  ),
))

export const signup = authLayout('Sign up', formCol(
  logo(), F('gap', { h: 12, w: 1 }),
  T('Sign up', 'pageTitle', { align: 'center' }),
  F('gap', { h: 8, w: 1 }),
  T('Create your account below', 'body', { align: 'center' }),
  F('Fields', { dir: 'v', gap: 12, sw: 'fill', pad: [20, 0, 0, 0], cross: 'center' },
    field('Name', input('Name', { placeholder: true })),
    field('Username', input('Username', { placeholder: true })),
    field('Email', input('Email', { placeholder: true })),
    row('Passwords', { gap: 12, sw: 'fill', cross: 'min' }, field('Password', passwordInput()), field('Confirm password', passwordInput())),
    row('Optional toggle', { gap: 6, sw: 'fill' }, I('chevron-down', '$primary', 16), T('Show optional fields', { size: 13, weight: 600, color: '$primary' })),
    button('Sign up', { sw: 'fill' }),
    T('Already have an account? Sign in', 'meta'),
  ),
), 700)

const narrowCard = (name, ...kids) => bare(name, card('Card', { w: 448, sw: 'fixed', pad: 32, gap: 0, cross: 'center' }, kids))

export const resetPassword = narrowCard('Reset password',
  logo(), F('gap', { h: 12, w: 1 }),
  T('Set a new password', 'cardHeading', { align: 'center' }),
  F('gap', { h: 8, w: 1 }),
  T('Choose a new password for your account.', 'body', { align: 'center' }),
  F('Fields', { dir: 'v', gap: 16, sw: 'fill', pad: [20, 0, 0, 0] },
    field('New password', passwordInput(), { hint: 'Use at least 8 characters.' }),
    field('Confirm new password', passwordInput()),
  ),
  F('gap', { h: 24, w: 1 }),
  button('Reset password', { sw: 'fill' }),
  F('gap', { h: 16, w: 1 }),
  T('Back to sign in', { size: 13, color: '$primary' }),
)

export const verifyEmail = narrowCard('Verify email',
  logo(), F('gap', { h: 12, w: 1 }),
  T('Email verified', 'cardHeading', { align: 'center' }),
  F('gap', { h: 8, w: 1 }),
  T('Your email address has been confirmed.', 'body', { align: 'center' }),
  F('gap', { h: 20, w: 1 }),
  F('Alert / info', { dir: 'h', gap: 8, pad: [10, 12], radius: 8, sw: 'fill', fill: C.info + '1A', stroke: C.info + '66', cross: 'center' },
    I('info', C.info, 16), T('Your account is now waiting for administrator approval.', { size: 13, color: '$foreground' }, { sw: 'fill' })),
  F('gap', { h: 24, w: 1 }),
  button('Continue to sign in'),
)

export const notFound = shell('Not found', card('Card', { pad: 32, cross: 'center', gap: 12 },
  F('gap', { h: 120, w: 1 }),
  T('404', { size: 44, weight: 600, color: C.brand }),
  T('Page not found', { size: 24, weight: 600, color: '$foreground' }),
  T('The page you are looking for does not exist or has moved', 'body', { align: 'center' }),
  button('Go to home'),
  F('gap', { h: 120, w: 1 }),
))
