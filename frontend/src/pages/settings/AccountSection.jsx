/**
 * frontend/src/pages/settings/AccountSection.jsx
 *
 * Shows: name, email, plan badge, license key, feature summary.
 * Edit mode: inline inputs for name and email.
 * On save: PUT /api/config + POST /api/email/save + sync to Render server.
 *
 * PROPS:
 *   local        full config clone (read only here)
 *   config       original config from server (for cancel reset)
 *   editName     string — current name input value
 *   setEditName  setter
 *   editEmail    string — current email input value
 *   setEditEmail setter
 *   editingId    bool — is edit mode active
 *   setEditingId setter
 *   savingId     bool — save in progress
 *   savedId      bool — save just completed (shows checkmark)
 *   saveIdentity function — calls API to save name + email
 *   navigate     react-router navigate function
 */

export default function AccountSection({
  local, config,
  editName, setEditName,
  editEmail, setEditEmail,
  editingId, setEditingId,
  savingId, savedId,
  saveIdentity, navigate
}) {
  const isPro = local.license?.tier === 'pro' || local.license?.tier === 'ultimate';

  return (
    <div className="bg-s-card border border-s-border rounded p-4">

      {/* Section header with Edit / Save / Cancel controls */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">
          Account
        </div>
        {!editingId ? (
          <button
            onClick={() => setEditingId(true)}
            className="text-[10px] text-s-accent hover:text-s-accent/80 transition-colors"
          >
            Edit
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => {
                setEditingId(false);
                setEditName(config?.identity?.user_name || '');
                setEditEmail(config?.email || '');
              }}
              className="text-[10px] text-s-text-4 hover:text-s-text-3"
            >
              Cancel
            </button>
            <button
              onClick={saveIdentity}
              disabled={savingId}
              className="text-[10px] text-s-accent font-medium"
            >
              {savingId ? 'Saving...' : savedId ? 'Saved' : 'Save'}
            </button>
          </div>
        )}
      </div>

      <div className="space-y-3">

        {/* Name row */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-s-text-3">Name</span>
          {editingId ? (
            <input
              value={editName}
              onChange={e => setEditName(e.target.value)}
              className="bg-s-bg border border-s-accent/30 rounded px-2.5 py-1 text-[11px] text-s-text w-40 focus:border-s-accent outline-none"
              placeholder="Your name"
              autoFocus
            />
          ) : (
            <span className="text-[11px] text-s-text font-medium">
              {local.identity?.user_name || '—'}
            </span>
          )}
        </div>

        {/* Email row */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-s-text-3">Email</span>
          {editingId ? (
            <input
              value={editEmail}
              onChange={e => setEditEmail(e.target.value)}
              type="email"
              className="bg-s-bg border border-s-accent/30 rounded px-2.5 py-1 text-[11px] text-s-text w-48 focus:border-s-accent outline-none font-mono"
              placeholder="you@email.com"
            />
          ) : (
            <span className="text-[11px] text-s-text font-mono truncate max-w-[200px]">
              {local.email || '—'}
            </span>
          )}
        </div>

        {/* Plan badge + action button */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-s-text-3">Plan</span>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-medium px-2 py-0.5 rounded ${
              isPro ? 'bg-s-accent/10 text-s-accent' : 'bg-s-border text-s-text-4'
            }`}>
              {local.license?.tier?.toUpperCase() || 'FREE'}
            </span>
            <button
              onClick={() => navigate('/plans')}
              className="text-[10px] text-s-accent hover:underline"
            >
              {isPro ? 'Manage' : 'Upgrade'}
            </button>
          </div>
        </div>

        {/* License key — only shown for paid tiers */}
        {isPro && local.license?.key && (
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-s-text-3">License</span>
            <span className="text-[10px] font-mono text-s-text-2">
              {local.license.key.slice(0, 12)}...
            </span>
          </div>
        )}

        {/* Plan feature summary + upgrade button */}
        <div className="mt-2 pt-2 border-t border-s-border/50">
          {(() => {
            const t = local.license?.tier || 'free';
            const featureMap = {
              free:     ['7 facts · 7 conversations · 1 file · 7 schedules · 3 aliases'],
              pro:      ['77 facts · 77 conversations · 7 files · 17 schedules · 7 aliases'],
              ultimate: ['Unlimited everything · Voice ID · Memory export · 3 devices'],
            };
            return (
              <div className="space-y-1.5">
                <div className="text-[10px] text-s-text-3 leading-relaxed">
                  {featureMap[t]?.[0]}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => navigate('/blog')}
                    className="text-[10px] px-2 py-1 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded hover:bg-s-accent/20"
                  >
                    How to use
                  </button>
                  {t !== 'ultimate' && (
                    <button
                      onClick={() => navigate('/plans')}
                      className="text-[10px] px-2 py-1 border border-s-border text-s-text-3 rounded hover:bg-s-card-h"
                    >
                      {t === 'free' ? 'Upgrade to Pro' : 'Upgrade to Ultimate'}
                    </button>
                  )}
                </div>
              </div>
            );
          })()}
        </div>

      </div>
    </div>
  );
}