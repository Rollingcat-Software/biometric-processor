import { useMutation } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { API_CONFIG } from '@/config/api.config';

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
  const filename = request.image instanceof File ? request.image.name : 'capture.jpg';
  formData.append('file', request.image, filename);
  if (request.threshold !== undefined) {
    formData.append('threshold', request.threshold.toString());
  }
  if (request.max_results !== undefined) {
    formData.append('max_results', request.max_results.toString());
  }

  // Use centralized API client with built-in retry, timeout, and error handling
  const data = await apiClient.upload<BackendSearchResponse>('/api/v1/search', formData, {
    timeout: REQUEST_TIMEOUT,
  });

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
}

export function useFaceSearch() {
  return useMutation({
    mutationFn: searchFace,
    mutationKey: ['face-search'],
  });
}
