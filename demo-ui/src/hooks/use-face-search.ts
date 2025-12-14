import { useMutation } from '@tanstack/react-query';
import { API_CONFIG } from '@/config/api.config';

const API_URL = API_CONFIG.BASE_URL;
const REQUEST_TIMEOUT = API_CONFIG.TIMEOUT.DEFAULT;

interface SearchRequest {
  image: File | Blob;
  threshold?: number;
  max_results?: number;
}

/**
 * Backend response format for search matches
 */
interface BackendSearchMatch {
  user_id: string;
  distance: number;
  confidence: number;
}

/**
 * Backend response format from /api/v1/search
 */
interface BackendSearchResponse {
  found: boolean;
  matches: BackendSearchMatch[];
  total_searched: number;
  threshold: number;
  best_match?: BackendSearchMatch;
  message: string;
}

/**
 * Frontend search match format
 */
interface SearchMatch {
  user_id: string;
  similarity: number;
  rank: number;
  // Preserve original backend fields
  distance: number;
  confidence: number;
}

/**
 * Frontend response format expected by demo UI
 */
interface SearchResponse {
  matches: SearchMatch[];
  total_searched: number;
  threshold: number;
  processing_time_ms: number;
  // Preserve original backend fields
  found: boolean;
  best_match?: SearchMatch;
  message: string;
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

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT);

  try {
    const response = await fetch(
      `${API_URL}/api/v1/search`,
      {
        method: 'POST',
        body: formData,
        signal: controller.signal,
      }
    );

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Search failed' }));
      throw new Error(error.message || error.detail);
    }

    const data: BackendSearchResponse = await response.json();

    // Map backend matches to frontend format
    const mappedMatches: SearchMatch[] = (data.matches || []).map((match, index) => ({
      user_id: match.user_id,
      similarity: match.confidence, // confidence maps to similarity (0-1)
      rank: index + 1,
      // Preserve original fields
      distance: match.distance,
      confidence: match.confidence,
    }));

    // Map best_match if present
    const mappedBestMatch: SearchMatch | undefined = data.best_match
      ? {
          user_id: data.best_match.user_id,
          similarity: data.best_match.confidence,
          rank: 1,
          distance: data.best_match.distance,
          confidence: data.best_match.confidence,
        }
      : undefined;

    return {
      matches: mappedMatches,
      total_searched: data.total_searched,
      threshold: data.threshold,
      processing_time_ms: 0, // Not provided by backend
      // Preserve original fields
      found: data.found,
      best_match: mappedBestMatch,
      message: data.message,
    };
  } finally {
    clearTimeout(timeoutId);
  }
}

export function useFaceSearch() {
  return useMutation({
    mutationFn: searchFace,
    mutationKey: ['face-search'],
  });
}
