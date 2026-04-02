import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useLicense from '../stores/useLicense';

export default function LicenseGate({ tier, feature, fallback, children }) {
  const { tier: currentTier, features } = useLicense();
  const navigate = useNavigate();
  const [showUpgrade, setShowUpgrade] = useState(false);

  // Check tier access
  const tierAllowed = () => {
    if (!tier) return true;
    const tiers = ['free', 'pro', 'ultimate'];
    const required = tiers.indexOf(tier);
    const current = tiers.indexOf(currentTier);
    return current >= required;
  };

  // Check feature limit
  const featureAllowed = () => {
    if (!feature) return true;
    const limit = features[feature];
    return limit === -1 || limit === true;
  };

  const allowed = tierAllowed() && featureAllowed();

  if (allowed) {
    return <>{children}</>;
  }

  // Show fallback or default upgrade prompt
  if (fallback) {
    return fallback;
  }

  return (
    <div className="bg-s-card border border-s-accent/20 rounded p-6 text-center">
      <div className="text-2xl mb-2">🔒</div>
      <div className="text-[13px] font-medium text-s-text mb-1">
        {tier ? `${tier.toUpperCase()} Feature` : 'Premium Feature'}
      </div>
      <p className="text-[11px] text-s-text-3 mb-4">
        Upgrade to unlock this feature
      </p>
      <button
        onClick={() => navigate('/plans')}
        className="px-4 py-2 border border-s-accent/30 bg-s-accent/10 text-s-accent rounded text-[11px] font-medium hover:bg-s-accent/20"
      >
        View Plans
      </button>
    </div>
  );
}