import axios from 'axios';

// Detect if we are in development mode on localhost or LAN
// If window.location.hostname is localhost or 127.0.0.1, use localhost
// Otherwise assume we are on LAN and try to use the same IP for backend
const getBaseUrl = () => {
  const hostname = window.location.hostname;
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:8000';
  }
  // For LAN access, assume backend is on the same IP as frontend but port 8000
  return `http://${hostname}:8000`;
};

export const API_BASE_URL = getBaseUrl();

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 60000, // 60 seconds timeout (increased for AI tasks)
});

// Add response interceptor for better error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.code === 'ECONNABORTED') {
      error.message = 'Request timeout - 后端服务器响应超时';
    } else if (error.code === 'ERR_NETWORK' || error.message.includes('Network Error')) {
      error.message = `Network Error - 无法连接到后端服务器。请确认后端是否在 ${API_BASE_URL} 运行`;
    } else if (error.response) {
      // Server responded with error status
      const status = error.response.status;
      const detail = error.response.data?.detail || error.response.data?.message || 'Unknown server error';
      error.message = `Server Error (${status}): ${detail}`;
    } else if (error.request) {
      // Request made but no response received
      error.message = 'No response from server - 后端服务器未响应';
    }
    return Promise.reject(error);
  }
);

export interface Job {
  id: string;
  company: string;
  role: string;
  location: string;
  url?: string;
  remote: boolean;
  match_score: number;
  tags: string[];
  status: 'not_applied' | 'applied' | 'skipped' | 'starred';
  source?: string; // Added source field
  jd_raw: string;
  visa_analysis?: string; // Added field
  jd_structured: {
    technical_stack: string;
    key_responsibilities: string;
    required_experience: string;
    success_metrics: string;
    salary_range: string;
    salary_is_estimated: boolean;
  };
  match_explanation: {
    strong_fit: string[];
    gaps: string[];
  };
  recommended_projects: {
    scope: string[];
    edge: string[];
    whisper: string[];
    alibaba?: string[];
    craes?: string[];
  };
  resume_versions?: Array<{
    pdf_path: string;
    text_path: string;
    version_id: string;
    created_at: string;
  }>;
}

export interface ResumeGenerationResult {
  pdf_path: string;
  text_path: string;
  version_id: string;
  created_at: string;
  bullets?: {
    scope?: string[];
    edge?: string[];
    whisper?: string[];
    alibaba?: string[];
    craes?: string[];
    [key: string]: string[] | undefined;
  };
}

export const jobsApi = {
  getAll: async (): Promise<Job[]> => {
    const response = await apiClient.get<Job[]>('/jobs');
    return response.data;
  },
  
  getById: async (id: string): Promise<Job> => {
    const response = await apiClient.get<Job>(`/jobs/${id}`);
    return response.data;
  },
  
  updateStatus: async (id: string, status: Job['status']): Promise<Job> => {
    const response = await apiClient.patch<Job>(`/jobs/${id}`, { status });
    return response.data;
  },
  
  apply: async (
    id: string, 
    onProgress?: (msg: string) => void
  ): Promise<ResumeGenerationResult> => {
    // Use fetch directly for SSE
    const response = await fetch(`${apiClient.defaults.baseURL}/jobs/${id}/apply`, {
      method: 'POST',
      headers: {
        'Accept': 'text/event-stream',
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to apply: ${response.statusText}`);
    }
    
    if (!response.body) {
      throw new Error('No response body');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalResult: ResumeGenerationResult | null = null;

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'progress') {
              onProgress?.(data.message);
            } else if (data.type === 'result') {
              finalResult = data.data;
            } else if (data.type === 'error') {
              throw new Error(data.message);
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    if (!finalResult) {
      throw new Error('Stream completed without result');
    }
    
    return finalResult;
  },

  openFolder: async (path: string): Promise<{ status: string; path: string }> => {
    const response = await apiClient.post('/jobs/open_folder', { path });
    return response.data;
  },

  deleteGenerated: async (id: string): Promise<{ status: string; deleted_paths: string[] }> => {
    const response = await apiClient.delete<{ status: string; deleted_paths: string[] }>(`/jobs/${id}/generated`);
    return response.data;
  },

  deleteJob: async (id: string): Promise<{ status: string; job_id: string; deleted_paths: string[] }> => {
    const response = await apiClient.delete<{ status: string; job_id: string; deleted_paths: string[] }>(`/jobs/${id}`);
    return response.data;
  },

  shutdown: async (): Promise<void> => {
    try {
      await apiClient.post('/shutdown');
    } catch (error) {
      // Expected error as server shuts down immediately
      console.log('Shutdown signal sent');
    }
  },

  generateCoverLetter: async (
    id: string,
    customPrompt?: string
  ): Promise<{ cover_letter: string; job_id: string; company: string; role: string }> => {
    const response = await apiClient.post(`/jobs/${id}/cover-letter`, {
      custom_prompt: customPrompt || ""
    });
    return response.data;
  },

  addManual: async (data: {
    title: string;
    company: string;
    location: string;
    description: string;
    url?: string;
    is_remote?: boolean;
  }): Promise<any> => {
    const response = await apiClient.post('/jobs/manual', data);
    return response.data;
  },

  addManualSimple: async (jd_text: string): Promise<any> => {
    const response = await apiClient.post('/jobs/manual-simple', { jd_text });
    return response.data;
  },
};

