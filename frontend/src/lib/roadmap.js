/**
 * What the welcome card says about Seven and where it is going. A short, honest summary of docs/product/roadmap.md,
 * in themes rather than version numbers, with no dates. Keep it in step with that page when something ships.
 */

export const ABOUT = {
  lead: 'Seven is the layer between you and your computer.',
  body: 'Today it listens, understands and acts on this PC, and everything stays on your device. We are building toward much more.',
  becoming: [
    'It will see your screen and use the mouse and keyboard for you.',
    'Give it a goal and it plans the steps, shows you, and does them.',
    'It will look after your PC and warn you before a problem starts.',
    'It will handle messages and email in your style, with your approval.',
    'It will follow you to your phone and your home.',
  ],
  feedback: 'Seven is early, and its first users shape it. Tell us what it misheard, what felt wrong and what you want first. Every note is read, and it decides what we build next.',
};

/**
 * now and next are one line each (titles only); later is the point of the tab, so each theme gets its own paragraph.
 */
export const ROADMAP = [
  {
    id: 'now',
    label: 'Working today',
    titles: ['Chat with memory', 'Natural voice', 'Apps, windows and system control', 'Reminders and tasks',
             'Your documents', 'Workspaces and triggers', 'Live answers'],
  },
  {
    id: 'next',
    label: 'Next',
    titles: ['Sharper understanding', 'Knows who is speaking', 'Natural conversation', 'Offline knowledge',
             'Chrome extension in the store'],
  },
  {
    id: 'later',
    label: 'Where Seven is going',
    items: [
      ['Seeing and using your screen',
       'Seven will read what is on your screen, understand it, and use the mouse and keyboard for you: click a button by its name, scroll, fill in a form, dictate into any app.'],
      ['Multi-step work',
       'Give Seven a goal and it plans the steps, shows you the plan, and carries it out. Download this PDF and summarise it. Tidy my Downloads. Plan my day. It retries what fails and tells you what happened.'],
      ['Looking after your PC',
       'It will watch memory, disk, battery and temperature, and speak up before something becomes a problem: your disk is almost full, this app is using 4 GB.'],
      ['Messages, calls and email',
       'Read, draft and send by voice, in your own style, and always with your approval first.'],
      ['Creating',
       'Write posts, make images and short videos, and publish them on a schedule you set.'],
      ['Your phone and your home',
       'Control your PC from your phone, run a standalone Seven on mobile, and drive your smart-home devices.'],
      ['Everyone, everywhere',
       'More than twenty languages, accessibility modes for blind, deaf and older users, and plugins from other developers.'],
      ['Safety and privacy at the core',
       'A safety shield for risky actions, your voice as a key, encrypted data, backup and restore, and one-click delete, all open to inspection.'],
    ],
  },
];
