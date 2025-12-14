import { useMutation } from '@tanstack/react-query';

interface SearchRequest {
  image: File | Blob;
  threshold?: number;
  max_results?: number;
}

interface SearchMatch {
  user_id: string;
  similarity: number;
  rank: number;
}

interface SearchResponse {
  matches: SearchMatch[];
  total_searched: number;
  threshold: number;
  processing_time_ms: number;
}

async function searchFace(request: SearchRequest): Promise<SearchResponse> {
  const formData = new FormData();
  formData.append('file', request.image);
  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }
  if (request.max_results !== undefined) {
    formData.append('max_results', request.max_results.toString());
  }

  const response = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'}/api/v1/search`,
    {
      method: 'POST',
      body: formData,
    }
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({ message: 'Search failed' }));
    throw new Error(error.message || error.detail);
  }

  return response.json();
}

export function useFaceSearch() {
  return useMutation({
    mutationFn: searchFace,
    mutationKey: ['face-search'],
  });
}
