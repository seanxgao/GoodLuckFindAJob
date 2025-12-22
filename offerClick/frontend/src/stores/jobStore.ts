import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface JobStore {
  selectedJobId: string | null;
  sortBy: 'match_score' | 'company' | 'date_added' | 'starred';
  filterStatus: 'all' | 'not_applied' | 'applied' | 'skipped' | 'starred' | 'manual';

  setSelectedJobId: (id: string | null) => void;
  setSortBy: (sort: JobStore['sortBy']) => void;
  setFilterStatus: (filter: JobStore['filterStatus']) => void;
}

export const useJobStore = create<JobStore>()(
  persist(
    (set) => ({
      selectedJobId: null,
      sortBy: 'company', // Changed default from match_score to company
      filterStatus: 'all',

      setSelectedJobId: (id) => set({ selectedJobId: id }),
      setSortBy: (sort) => set({ sortBy: sort }),
      setFilterStatus: (filter) => set({ filterStatus: filter }),
    }),
    {
      name: 'job-store', // localStorage key
    }
  )
);

