/** App-wide toast notifications. Render <Toaster /> once (App.jsx); call toast.success(...) anywhere. */
import { create } from 'zustand';

export const useToasts = create(set => ({
  items: [],
  push: (t) => {
    const id = Math.random().toString(36).slice(2);
    set(s => ({ items: [...s.items.slice(-3), { id, ...t }] }));
    setTimeout(() => set(s => ({ items: s.items.filter(i => i.id !== id) })), t.duration || 2600);
  },
  dismiss: id => set(s => ({ items: s.items.filter(i => i.id !== id) })),
}));

export const toast = {
  success: (title, description) => useToasts.getState().push({ tone: 'success', title, description }),
  error: (title, description) => useToasts.getState().push({ tone: 'error', title, description, duration: 4500 }),
  info: (title, description) => useToasts.getState().push({ tone: 'info', title, description }),
};
