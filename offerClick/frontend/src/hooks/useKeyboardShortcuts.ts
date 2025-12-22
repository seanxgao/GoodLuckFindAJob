import { useHotkeys } from 'react-hotkeys-hook';
import { useJobStore } from '../stores/jobStore';
import type { Job } from '../api/client';

export function useKeyboardShortcuts(
  jobs: Job[],
  onApply: (jobId: string) => void,
  onSkip: (jobId: string) => void,
  onStar: (jobId: string) => void
) {
  const { selectedJobId, setSelectedJobId, sortBy } = useJobStore();

  // Get sorted/filtered jobs for navigation
  const sortedJobs = [...jobs].sort((a, b) => {
    switch (sortBy) {
      case 'match_score':
        return b.match_score - a.match_score;
      case 'company':
        return a.company.localeCompare(b.company);
      case 'starred':
        if (a.status === 'starred' && b.status !== 'starred') return -1;
        if (a.status !== 'starred' && b.status === 'starred') return 1;
        return b.match_score - a.match_score;
      default:
        return 0;
    }
  });

  const currentIndex = selectedJobId
    ? sortedJobs.findIndex((j) => j.id === selectedJobId)
    : -1;

  // J: Next job
  useHotkeys('j', (e) => {
    e.preventDefault();
    if (currentIndex < sortedJobs.length - 1) {
      setSelectedJobId(sortedJobs[currentIndex + 1].id);
    }
  }, { enableOnFormTags: true });

  // K: Previous job
  useHotkeys('k', (e) => {
    e.preventDefault();
    if (currentIndex > 0) {
      setSelectedJobId(sortedJobs[currentIndex - 1].id);
    }
  }, { enableOnFormTags: true });

  // Enter: Open/select job (already handled by click, but for consistency)
  useHotkeys('enter', (e) => {
    if (selectedJobId) {
      // Job is already selected, this is just for consistency
      e.preventDefault();
    }
  }, { enableOnFormTags: true });

  // A: Apply
  useHotkeys('a', (e) => {
    e.preventDefault();
    if (selectedJobId) {
      onApply(selectedJobId);
    }
  }, { enableOnFormTags: true });

  // S: Skip
  useHotkeys('s', (e) => {
    e.preventDefault();
    if (selectedJobId && !e.shiftKey) {
      onSkip(selectedJobId);
    }
  }, { enableOnFormTags: true });

  // Shift+S: Star
  useHotkeys('shift+s', (e) => {
    e.preventDefault();
    if (selectedJobId) {
      onStar(selectedJobId);
    }
  }, { enableOnFormTags: true });
}

