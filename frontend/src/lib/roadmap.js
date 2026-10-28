/**
 * What the welcome card says about Seven and where it is going. A short, honest summary of docs/product/roadmap.md,
 * in themes rather than version numbers, with no dates. Keep it in step with that page when something ships.
 */

export const ABOUT = {
  lead: 'Seven is the layer between you and your computer.',
  body: [
    'Today it listens, understands and acts on this PC. In time it will see your screen, plan and carry out multi-step work, handle your messages, and reach your phone and your home.',
    'The aim is an assistant that can do whatever you can do at a computer, and runs on your own device while it does.',
  ],
  stands: [
    ['Local first', 'It runs on your PC. Your conversations and memory stay with you.'],
    ['Yours', 'It remembers you, and can show where it learned each thing.'],
    ['Acts, not only answers', 'Opens, arranges, controls and schedules, and says plainly when something did not work.'],
    ['You stay in control', 'It asks before anything risky, and nothing is sent or posted without your approval.'],
    ['Built with you', 'Each beta release is shaped by what you tell us.'],
  ],
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
