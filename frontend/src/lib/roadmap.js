/**
 * What the welcome card's Roadmap tab shows: a short, honest summary of docs/product/roadmap.md, in themes rather
 * than version numbers, with no dates. Keep it in step with that page when something ships.
 *   now    works in this beta
 *   next   being worked on
 *   later  planned, in no fixed order
 */
export const ROADMAP = [
  {
    id: 'now',
    label: 'In this beta',
    items: [
      ['Chat with memory', 'Seven remembers what you tell it, and can show where it learned it.'],
      ['Natural voice', 'Say "Hey Seven". Replies start as soon as the first sentence is ready.'],
      ['Control your PC', 'Apps, windows, volume, brightness, Wi-Fi, Bluetooth and dark mode.'],
      ['Reminders and tasks', 'Reminders, alarms, timers and repeating events.'],
      ['Your documents', 'Ask questions about your PDFs and notes, with page references.'],
      ['Workspaces and triggers', 'Save everything you have open and bring it back by voice, hotkey, snap or clap.'],
      ['Live answers', 'Optional web lookups, and honest when you are offline.'],
    ],
  },
  {
    id: 'next',
    label: 'Next',
    items: [
      ['Sharper understanding', 'Fewer misheard or misrouted commands, and clearer confirmation when Seven acts.'],
      ['Knows who is speaking', 'Separate profiles and memory for each person on the PC.'],
      ['Natural conversation', 'Talk over Seven and keep the thread going, not only stop it.'],
      ['Offline knowledge', 'Answers from a downloaded encyclopedia, with no internet.'],
      ['Chrome extension in the store', 'Install it in one click.'],
    ],
  },
  {
    id: 'later',
    label: 'Later',
    items: [
      ['Seeing and using your screen', 'Read what is on screen, click buttons by name, scroll, fill forms and dictate into any app.'],
      ['Multi-step tasks', 'Plans you approve first, daily routines, file organising, PC health alerts and day planning.'],
      ['Messages and calls', 'Read and reply by voice, always with your approval before anything is sent.'],
      ['Creating', 'Writing, images and scheduled posts.'],
      ['Phone and home', 'Control your PC from your phone, a mobile Seven, and smart-home devices.'],
      ['Safety and polish', 'Confirmation already guards risky actions; a fuller safety shield, backup and restore, more languages and plugins are planned.'],
    ],
  },
];
