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
    <div className="bg-white/[0.02] border border-white/8 rounded-2xl overflow-hidden">
      <div className="px-5 py-4 border-b border-white/[0.05] flex items-center justify-between">
        <div>
          <h2 className="text-[12px] font-semibold text-white/85">Profile</h2>
          <p className="text-[9px] text-white/35 mt-0.5">Your account details and plan</p>
        </div>
        {!editingId ? (
          <button
            onClick={() => setEditingId(true)}
            className="text-[10px] text-s-accent/80 hover:text-s-accent
                       px-3 py-1 rounded-lg hover:bg-s-accent/8 transition-all"
          >
            Edit
          </button>
        ) : (
          <div className="flex gap-1">
            <button
              onClick={() => {
                setEditingId(false);
                setEditName(config?.identity?.user_name || '');
                setEditEmail(config?.email || '');
              }}
              className="text-[10px] text-white/35 hover:text-white/60 px-3 py-1 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={saveIdentity}
              disabled={savingId}
              className="text-[10px] text-s-accent font-medium px-3 py-1
                         bg-s-accent/8 border border-s-accent/15 rounded-lg
                         hover:bg-s-accent/15 transition-all"
            >
              {savingId ? 'Saving...' : savedId ? 'Saved' : 'Save'}
            </button>
          </div>
        )}
      </div>

      <div className="p-5 space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-white/55">Name</span>
          {editingId ? (
            <input
              value={editName}
              onChange={e => setEditName(e.target.value)}
              className="bg-white/[0.03] border border-s-accent/25 rounded-lg px-3 py-1.5
                         text-[11px] text-white/80 w-48 focus:border-s-accent/50 outline-none
                         transition-colors"
              placeholder="Your name"
              autoFocus
            />
          ) : (
            <span className="text-[11px] text-white/90 font-medium">
              {local.identity?.user_name || '—'}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[11px] text-white/55">Email</span>
          {editingId ? (
            <input
              value={editEmail}
              onChange={e => setEditEmail(e.target.value)}
              type="email"
              className="bg-white/[0.03] border border-s-accent/25 rounded-lg px-3 py-1.5
                         text-[11px] text-white/80 w-56 focus:border-s-accent/50 outline-none
                         transition-colors font-mono"
              placeholder="you@email.com"
            />
          ) : (
            <span className="text-[11px] text-white/80 font-mono truncate max-w-[240px]">
              {local.email || '—'}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between">
          <span className="text-[11px] text-white/55">Plan</span>
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-semibold px-2.5 py-0.5 rounded-md border
              ${isPro
                ? 'bg-s-accent/10 text-s-accent border-s-accent/20'
                : 'bg-white/[0.03] text-white/50 border-white/8'}`}>
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

        {isPro && local.license?.key && (
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-white/55">License</span>
            <span className="text-[10px] font-mono text-white/60">
              {local.license.key.slice(0, 12)}...
            </span>
          </div>
        )}

        <div className="pt-4 border-t border-white/[0.05]">
          {(() => {
            const t = local.license?.tier || 'free';
            const featureMap = {
              free: ['7 facts · 7 conversations · 1 file · 7 schedules · 3 aliases'],
              pro: ['77 facts · 77 conversations · 7 files · 17 schedules · 7 aliases'],
              ultimate: ['Unlimited everything · Voice ID · Memory export · 3 devices'],
            };
            return (
              <div className="space-y-3">
                <p className="text-[10.5px] text-white/55 leading-relaxed">
                  {featureMap[t]?.[0]}
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => navigate('/blog')}
                    className="text-[10px] px-3 py-1.5 border border-s-accent/20 bg-s-accent/8
                               text-s-accent rounded-lg hover:bg-s-accent/15 transition-all"
                  >
                    How to use
                  </button>
                  {t !== 'ultimate' && (
                    <button
                      onClick={() => navigate('/plans')}
                      className="text-[10px] px-3 py-1.5 border border-white/8 text-white/55
                                 rounded-lg hover:bg-white/[0.03] hover:text-white/75 transition-all"
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