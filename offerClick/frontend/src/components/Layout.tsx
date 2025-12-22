import type { ReactNode } from 'react';
import { Power } from 'lucide-react';
import { jobsApi } from '../api/client';

interface LayoutProps {
  queuePanel: ReactNode;
  mainPanel: ReactNode;
  previewPanel: ReactNode;
  breadcrumb?: ReactNode;
}

export function Layout({ queuePanel, mainPanel, previewPanel, breadcrumb }: LayoutProps) {
  const handleShutdown = async () => {
    if (confirm('Are you sure you want to shutdown both backend and frontend?')) {
      try {
        // Kill backend
        await jobsApi.shutdown();
      } finally {
        // Close browser tab
        window.close();
        // If window.close() is blocked, at least show a message
        document.body.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;height:100vh;font-family:sans-serif;"><h1>System Shutdown. You can close this tab.</h1></div>';
      }
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-gray-100">
      {/* Header with Breadcrumb */}
      {breadcrumb && (
        <div className="h-12 flex-shrink-0 bg-white border-b border-gray-200 flex items-center justify-between px-4 shadow-sm">
          <div className="flex-1">
            {breadcrumb}
          </div>
          {/* Shutdown Button - moved to header */}
          <button
            onClick={handleShutdown}
            className="p-2 bg-red-100 text-red-600 rounded-full hover:bg-red-200 transition-colors"
            title="Shutdown Application"
          >
            <Power className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Shutdown button fallback if no breadcrumb */}
        {!breadcrumb && (
          <button
            onClick={handleShutdown}
            className="absolute top-2 right-2 z-50 p-2 bg-red-100 text-red-600 rounded-full hover:bg-red-200 transition-colors shadow-sm"
            title="Shutdown Application"
          >
            <Power className="w-5 h-5" />
          </button>
        )}

        {/* Left Sidebar - Job Queue */}
        <div className="w-80 flex-shrink-0 border-r border-gray-200 bg-white z-10">
          {queuePanel}
        </div>

        {/* Main Content Area */}
        <div className="flex-1 flex min-w-0">
          {/* Main Panel - Info & Actions (Merged) */}
          <div className="w-96 flex-shrink-0 border-r border-gray-200">
            {mainPanel}
          </div>

          {/* Right Panel - Resume PDF Preview */}
          <div className="flex-1 min-w-0 bg-gray-50">
            {previewPanel}
          </div>
        </div>
      </div>
    </div>
  );
}

