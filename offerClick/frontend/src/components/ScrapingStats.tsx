import React, { useEffect, useState } from 'react';
import { jobsApi } from '../api/client';

interface StatsData {
  last_fetch_time: string | null;
  total_fetched: number;
  total_passed_screening: number;
  total_visa_blocked: number;
  total_senior_blocked: number;
  total_match_failed: number;
  applied_count: number;
  pass_rate: number;
}

export const ScrapingStats: React.FC = () => {
  const [stats, setStats] = useState<StatsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadStats = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await jobsApi.getScrapingStats();
      setStats(data);
    } catch (err) {
      setError('Failed to load stats');
      console.error('Stats error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStats();
    // Refresh stats every 60 seconds
    const interval = setInterval(loadStats, 60000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 text-sm">
        <div className="text-gray-400">Loading stats...</div>
      </div>
    );
  }

  if (error && !stats) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 text-sm">
        <div className="text-red-400">{error}</div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="bg-gray-800 rounded-lg p-4 text-sm space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-100">Scraping Stats</h3>
        <button
          onClick={loadStats}
          className="text-xs text-blue-400 hover:text-blue-300"
          title="Refresh stats"
        >
          Refresh
        </button>
      </div>

      {/* Last Fetch */}
      <div className="text-xs text-gray-400">
        Last Fetch: {stats.last_fetch_time || 'Never'}
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-700 rounded p-2">
          <div className="text-xs text-gray-400">Total Fetched</div>
          <div className="text-lg font-bold text-blue-400">{stats.total_fetched}</div>
        </div>

        <div className="bg-gray-700 rounded p-2">
          <div className="text-xs text-gray-400">Passed</div>
          <div className="text-lg font-bold text-green-400">{stats.total_passed_screening}</div>
        </div>

        <div className="bg-gray-700 rounded p-2">
          <div className="text-xs text-gray-400">Visa Blocked</div>
          <div className="text-lg font-bold text-red-400">{stats.total_visa_blocked}</div>
        </div>

        <div className="bg-gray-700 rounded p-2">
          <div className="text-xs text-gray-400">Senior Blocked</div>
          <div className="text-lg font-bold text-orange-400">{stats.total_senior_blocked}</div>
        </div>

        <div className="bg-gray-700 rounded p-2">
          <div className="text-xs text-gray-400">Match Failed</div>
          <div className="text-lg font-bold text-yellow-400">{stats.total_match_failed}</div>
        </div>

        <div className="bg-gray-700 rounded p-2">
          <div className="text-xs text-gray-400">Applied</div>
          <div className="text-lg font-bold text-purple-400">{stats.applied_count}</div>
        </div>
      </div>

      {/* Pass Rate */}
      <div className="bg-gray-700 rounded p-2">
        <div className="text-xs text-gray-400 mb-1">Pass Rate</div>
        <div className="flex items-center gap-2">
          <div className="flex-1 bg-gray-600 rounded-full h-2">
            <div
              className="bg-green-500 h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(stats.pass_rate, 100)}%` }}
            />
          </div>
          <div className="text-sm font-semibold text-green-400">{stats.pass_rate}%</div>
        </div>
      </div>
    </div>
  );
};
