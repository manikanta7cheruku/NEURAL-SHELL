import { useNavigate } from 'react-router-dom';

export default function UpgradePrompt({ feature, tier = 'pro' }) {
  const navigate = useNavigate();

  return (
    <div className="bg-gradient-to-br from-s-accent/5 to-s-accent/10 border border-s-accent/20 rounded p-4">
      <div className="flex items-start gap-3">
        <div className="text-2xl">⭐</div>
        <div className="flex-1">
          <div className="text-[12px] font-medium text-s-text mb-1">
            Unlock {feature || 'Premium Features'}
          </div>
          <p className="text-[10px] text-s-text-3 mb-3">
            Upgrade to {tier.toUpperCase()} to access this feature and more
          </p>
          <button
            onClick={() => navigate('/plans')}
            className="px-3 py-1.5 border border-s-accent/30 bg-s-accent/8 text-s-accent rounded text-[10px] font-medium hover:bg-s-accent/20"
          >
            Upgrade Now
          </button>
        </div>
      </div>
    </div>
  );
}