/** Join class names, skipping falsy values. */
export const cx = (...c) => c.filter(Boolean).join(' ');
