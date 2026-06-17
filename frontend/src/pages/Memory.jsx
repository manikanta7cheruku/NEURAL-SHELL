import { useEffect, useState } from 'react';
import useMemory from '../stores/useMemory';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';
import api from '../api';
import useConfig from '../stores/useConfig';

export default function Memory() {
  const { config } = useConfig();
  const tier = config?.license?.tier || 'free';
  const convLimit = { free: 7, pro: 77, ultimate: null }[tier];
  const factLimit = { free: 7, pro: 77, ultimate: null }[tier];
  const [tab, setTab] = useState('facts');
  const [search, setSearch] = useState('');
  const [newFact, setNewFact] = useState('');
  const [adding, setAdding] = useState(false);
  const { facts, conversations, totalConvos, stats, loading, fetchFacts, fetchConvos, fetchStats, deleteFact, deleteConvo } = useMemory();

  useEffect(() => { fetchFacts(); fetchConvos(); fetchStats(); }, []);

  const addFact = async () => { if (!newFact.trim()) return; await api.post('/chat', { text: `/add fact ${newFact.trim()}` }); setNewFact(''); setAdding(false); fetchFacts(); };

  if (loading) return <Spinner t="Loading..." />;
  const ff = search ? facts.filter(f => f.text.toLowerCase().includes(search.toLowerCase())) : facts;
  const cf = search ? conversations.filter(c => (c.user_input + c.seven_response).toLowerCase().includes(search.toLowerCase())) : conversations;

  return (
    <div className="h-full flex flex-col">
      <PageHeader title="Memory" sub="Everything Seven has learned, stored locally on your disk" />
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {stats && (
          <div className="grid grid-cols-4 gap-2">

        {/* ── Limit banners ── */}
        {stats && (() => {
          const tier = stats.tier || 'free';
          const limits = { free: 7, pro: 77, ultimate: null };
          const convLimit = limits[tier];
          const factLimit = { free: 7, pro: 77, ultimate: null }[tier];
          const convNearLimit = convLimit && stats.total_conversations >= convLimit * 0.9;
          const factNearLimit = factLimit && stats.total_facts >= factLimit * 0.9;
          const convAtLimit = convLimit && stats.total_conversations >= convLimit;
          const factAtLimit = factLimit && stats.total_facts >= factLimit;

          return (
            <>
              {convAtLimit && (
                <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-s-accent/5 border border-s-accent/20">
                  <div className="flex items-center gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-s-accent animate-pulse flex-shrink-0" />
                    <div>
                      <div className="text-[11px] text-s-text-2 font-medium">
                        Conversation memory full
                      </div>
                      <div className="text-[9px] text-s-text-4 mt-0.5">
                        {tier === 'pro'
                          ? `Pro limit: ${convLimit} conversations. Upgrade to Ultimate for unlimited.`
                          : `Free limit: ${convLimit} conversations. Upgrade for more.`}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => window.__navigate?.('/plans')}
                    className="text-[10px] text-s-accent font-medium hover:underline shrink-0 ml-3"
                  >
                    Upgrade
                  </button>
                </div>
              )}
              {factAtLimit && (
                <div className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-yellow-500/5 border border-yellow-500/20">
                  <div className="flex items-center gap-2.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-yellow-400 animate-pulse flex-shrink-0" />
                    <div>
                      <div className="text-[11px] text-s-text-2 font-medium">
                        Facts memory full
                      </div>
                      <div className="text-[9px] text-s-text-4 mt-0.5">
                        {tier === 'pro'
                          ? `Pro limit: ${factLimit} facts. Upgrade to Ultimate for unlimited.`
                          : `Free limit: ${factLimit} facts. Upgrade for more.`}
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => window.__navigate?.('/plans')}
                    className="text-[10px] text-yellow-400 font-medium hover:underline shrink-0 ml-3"
                  >
                    Upgrade
                  </button>
                </div>
              )}
            </>
          );
        })()}


            {[['Facts', stats.total_facts], ['Conversations', stats.total_conversations], ['DB Size', `${stats.storage_mb || 0} MB`], ['Storage', 'Local disk']].map(([l, v]) => (
              <div key={l} className="bg-s-card border border-s-border rounded px-3 py-2">
                <div className="text-[9px] text-s-text-4 uppercase tracking-wider font-medium">{l}</div>
                <div className="text-[13px] font-medium text-s-text mt-1 font-mono">{v}</div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1.5">
          {['facts', 'conversations'].map(t => (
            <button key={t} onClick={() => setTab(t)} className={`px-2.5 py-1.5 rounded text-[11px] capitalize font-medium ${tab === t ? 'bg-s-accent/8 text-s-accent' : 'text-s-text-3'}`}>{t}</button>
          ))}
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search..." className="ml-auto w-44 bg-s-card border border-s-border rounded px-2 py-1 text-[11px] text-s-text placeholder-s-text-4" />
          {tab === 'facts' && <button onClick={() => setAdding(!adding)} className="text-[10px] text-s-accent font-medium">+ Add</button>}
        </div>

        {adding && (
          <div className="bg-s-card border border-s-border rounded p-2.5 flex gap-2">
            <input value={newFact} onChange={e => setNewFact(e.target.value)} autoFocus onKeyDown={e => e.key === 'Enter' && addFact()} placeholder="Enter a fact..." className="flex-1 bg-s-bg border border-s-border rounded px-2 py-1.5 text-[11px] text-s-text placeholder-s-text-4" />
            <button onClick={addFact} className="text-[10px] text-s-accent font-medium px-2">Save</button>
            <button onClick={() => setAdding(false)} className="text-[10px] text-s-text-4 px-2">Cancel</button>
          </div>
        )}

        {tab === 'facts' && (
          <div className="space-y-px">
            {ff.length === 0 && <div className="py-5 text-center text-[11px] text-s-text-4">No facts</div>}
            {ff.map(f => (
              <div key={f.id} className="flex items-start gap-2 px-3 py-2 rounded bg-s-card border border-s-border hover:bg-s-card-h group">
                <div className="flex-1 min-w-0">
                  <p className="text-[12px] text-s-text-2 leading-relaxed">{f.text}</p>
                  <div className="flex gap-2 mt-1"><span className="text-[8px] text-s-accent bg-s-accent/8 px-1.5 py-0.5 rounded font-medium">{f.category}</span><span className="text-[8px] text-s-text-4">{f.timestamp?.split(' ')[0]}</span></div>
                </div>
                <button onClick={() => deleteFact(f.id)} className="text-[9px] text-s-text-4 hover:text-s-red opacity-0 group-hover:opacity-100">del</button>
              </div>
            ))}
          </div>
        )}

        {tab === 'conversations' && (
          <div className="space-y-px">
            {cf.length === 0 && <div className="py-5 text-center text-[11px] text-s-text-4">No conversations</div>}
            {cf.map(c => (
              <div key={c.id} className="px-3 py-2 rounded bg-s-card border border-s-border hover:bg-s-card-h group">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0 space-y-1">
                    {c.user_input && <div className="text-[12px]"><span className="text-[8px] text-s-accent font-medium font-mono mr-1.5">YOU</span><span className="text-s-text-2">{c.user_input}</span></div>}
                    {c.seven_response && <div className="text-[12px]"><span className="text-[8px] text-s-cyan font-medium font-mono mr-1.5">VII</span><span className="text-s-text-3">{c.seven_response}</span></div>}
                    <div className="text-[8px] text-s-text-4 font-mono">{c.timestamp}</div>
                  </div>
                  <button onClick={() => deleteConvo(c.id)} className="text-[9px] text-s-text-4 hover:text-s-red opacity-0 group-hover:opacity-100 ml-2">del</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}