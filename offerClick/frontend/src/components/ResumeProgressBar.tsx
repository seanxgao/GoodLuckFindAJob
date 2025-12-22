import { Check, Loader2, Clock } from 'lucide-react';
import { useMemo } from 'react';

interface Task {
  id: string;
  label: string;
  description: string;
  startKeywords: string[];
  completeKeywords: string[];
}

const RESUME_GENERATION_TASKS: Task[] = [
  {
    id: 'init',
    label: 'Initialize',
    description: 'Loading job description and context',
    startKeywords: ['=== Processing JD'],
    completeKeywords: ['-> Using provided JD text directly']
  },
  {
    id: 'skills',
    label: 'Skills Selection',
    description: 'Generating resume skills and filename',
    startKeywords: ['-> Generating Skills & Filename'],
    completeKeywords: ['-> Target:']
  },
  {
    id: 'filtering',
    label: 'Filter Facts',
    description: 'Extracting relevant experience (5 async tasks)',
    startKeywords: ['-> [Async] Filtering facts for all sections in parallel'],
    completeKeywords: ['-> [Async] Generating bullets for all sections in parallel']
  },
  {
    id: 'bullets',
    label: 'Generate Content',
    description: 'Writing resume bullets (5 async tasks)',
    startKeywords: ['-> [Async] Generating bullets for all sections in parallel'],
    completeKeywords: ['-> [Async] Converting bullets to LaTeX in parallel']
  },
  {
    id: 'latex',
    label: 'Format LaTeX',
    description: 'Converting to LaTeX format (5 async tasks)',
    startKeywords: ['-> [Async] Converting bullets to LaTeX in parallel'],
    completeKeywords: ['[OK] Saved raw bullets']
  },
  {
    id: 'compile',
    label: 'Compile PDF',
    description: 'Building final PDF document',
    startKeywords: ['[*] Compiling PDF using'],
    completeKeywords: ['[OK] Built PDF']
  },
  {
    id: 'complete',
    label: 'Complete',
    description: 'Resume generation finished',
    startKeywords: ['[OK] Built PDF'],
    completeKeywords: ['[Done] Resume generation complete']
  }
];

interface ResumeProgressBarProps {
  logs: string[];
}

type TaskStatus = 'pending' | 'in-progress' | 'completed';

export function ResumeProgressBar({ logs }: ResumeProgressBarProps) {
  const taskStatuses = useMemo(() => {
    const fullLog = logs.join('\n');

    return RESUME_GENERATION_TASKS.map(task => {
      // Check if task is completed
      const isCompleted = task.completeKeywords.some(keyword =>
        fullLog.includes(keyword)
      );

      if (isCompleted) {
        return { taskId: task.id, status: 'completed' as TaskStatus };
      }

      // Check if task is in progress
      const isStarted = task.startKeywords.some(keyword =>
        fullLog.includes(keyword)
      );

      if (isStarted) {
        return { taskId: task.id, status: 'in-progress' as TaskStatus };
      }

      // Task is pending
      return { taskId: task.id, status: 'pending' as TaskStatus };
    });
  }, [logs]);

  const completedCount = taskStatuses.filter(t => t.status === 'completed').length;
  const progress = (completedCount / RESUME_GENERATION_TASKS.length) * 100;

  return (
    <div className="bg-white rounded-lg p-4 border border-gray-200 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-gray-700">Resume Generation</h4>
        <span className="text-xs text-gray-500">
          {completedCount}/{RESUME_GENERATION_TASKS.length} tasks
        </span>
      </div>

      {/* Overall progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-1.5 overflow-hidden">
        <div
          className="bg-blue-600 h-full rounded-full transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Task checklist */}
      <div className="space-y-2">
        {RESUME_GENERATION_TASKS.map((task, index) => {
          const status = taskStatuses[index].status;
          const isCompleted = status === 'completed';
          const isInProgress = status === 'in-progress';
          const isPending = status === 'pending';

          return (
            <div
              key={task.id}
              className="flex items-start gap-2 text-xs"
            >
              {/* Icon */}
              <div className="flex-shrink-0 mt-0.5">
                {isCompleted && <Check className="w-4 h-4 text-green-600" />}
                {isInProgress && <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />}
                {isPending && <Clock className="w-4 h-4 text-gray-300" />}
              </div>

              {/* Task info */}
              <div className="flex-1 min-w-0">
                <div className={`font-medium ${
                  isCompleted ? 'text-green-600' :
                  isInProgress ? 'text-blue-600' :
                  'text-gray-400'
                }`}>
                  {task.label}
                </div>
                <div className={`text-xs ${
                  isCompleted ? 'text-green-500/70' :
                  isInProgress ? 'text-blue-500/70' :
                  'text-gray-400'
                }`}>
                  {task.description}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
