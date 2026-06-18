/**
 * ConversationPanel.jsx
 * 
 * Shows what the user said and what Seven replied.
 * Sits below the Orb in the status window (status.html)
 * OR floats in the main window near the orb area.
 * 
 * Design: Clean, minimal, glassmorphic. No slide animations.
 * Text simply appears with a soft fade. Professional.
 * 
 * HOW IT WORKS:
 *   useStatus store receives user_text + seven_text from WebSocket
 *   This component reads them and displays with auto-scroll
 *   Fades out 6 seconds after Seven stops speaking
 */

import { useEffect, useRef, useState } from 'react';
import useStatus from '../stores/useStatus';

export default function ConversationPanel() {
  const { userText, sevenText, listening, thinking, speaking, connected } = useStatus();
  const sevenRef   = useRef(null);
  const [visible,  setVisible]  = useState(false);
  const [fadeOut,  setFadeOut]  = useState(false);
  const fadeTimer  = useRef(null);

  // Show panel whenever there is content
  useEffect(() => {
    if (userText || sevenText || thinking || speaking) {
      setVisible(true);
      setFadeOut(false);
      if (fadeTimer.current) clearTimeout(fadeTimer.current);
    }
  }, [userText, sevenText, thinking, speaking]);

  // Fade out 5 seconds after Seven finishes speaking and is back to listening
  useEffect(() => {
    if (!speaking && !thinking && visible && (userText || sevenText)) {
      if (fadeTimer.current) clearTimeout(fadeTimer.current);
      fadeTimer.current = setTimeout(() => {
        setFadeOut(true);
        setTimeout(() => setVisible(false), 800); // wait for fade animation
      }, 5000);
    }
    return () => { if (fadeTimer.current) clearTimeout(fadeTimer.current); };
  }, [speaking, thinking, sevenText]);

  // Auto-scroll Seven's text as it streams in
  useEffect(() => {
    if (sevenRef.current) {
      sevenRef.current.scrollTop = sevenRef.current.scrollHeight;
    }
  }, [sevenText]);

  if (!connected) return null;
  if (!visible && !userText && !sevenText && !thinking && !speaking) return null;

  return (
    <div
      className={`transition-all duration-700 ease-out ${
        fadeOut ? 'opacity-0 translate-y-1' : 'opacity-100 translate-y-0'
      }`}
    >
      <div
        className="rounded-xl border border-white/8 overflow-hidden"
        style={{
          background:   'rgba(9, 9, 11, 0.75)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          boxShadow:    '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.06)',
        }}
      >
        {/* User line */}
        {userText && (
          <div className="px-4 pt-3 pb-2 flex items-start gap-2.5">
            <div className="w-1.5 h-1.5 rounded-full bg-white/30 mt-1.5 shrink-0" />
            <p className="text-[11px] text-white/50 leading-relaxed font-light">
              {userText}
            </p>
          </div>
        )}

        {/* Divider between user and seven */}
        {userText && (sevenText || thinking) && (
          <div className="mx-4 h-px bg-white/5" />
        )}

        {/* Seven's response */}
        {(sevenText || thinking) && (
          <div className="px-4 pt-2 pb-3 flex items-start gap-2.5">
            {/* Accent dot — pulses while speaking */}
            <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 bg-s-accent ${
              speaking ? 'animate-pulse' : ''
            }`} />

            {thinking && !sevenText ? (
              /* Thinking dots */
              <div className="flex items-center gap-1 py-0.5">
                {[0, 1, 2].map(i => (
                  <div
                    key={i}
                    className="w-1 h-1 rounded-full bg-s-accent/60"
                    style={{ animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite` }}
                  />
                ))}
              </div>
            ) : (
              /* Seven's text — scrollable for long responses */
              <div
                ref={sevenRef}
                className="text-[12px] text-white/85 leading-relaxed font-light max-h-32 overflow-y-auto scrollbar-none"
              >
                {sevenText}
                {/* Blinking cursor while speaking */}
                {speaking && (
                  <span className="inline-block w-0.5 h-3 bg-s-accent ml-0.5 animate-pulse align-middle" />
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}