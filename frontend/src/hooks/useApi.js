import { useState, useEffect, useCallback, useRef } from 'react'

export function useApi(url, options = {}) {
  const { refreshInterval, enabled = true } = options
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(!!url)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)

  const fetchData = useCallback(async () => {
    if (!enabled || !url) {
      setLoading(false)
      return
    }
    try {
      const res = await fetch(url, { credentials: 'include' })
      if (!res.ok) {
        if (res.status === 401) {
          setData(null)
          setError('auth')
          return
        }
        throw new Error(`HTTP ${res.status}`)
      }
      const json = await res.json()
      setData(json)
      setError(null)
    } catch (e) {
      console.error('API fetch error:', url, e.message)
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [url, enabled])

  useEffect(() => {
    fetchData()
    if (refreshInterval) {
      intervalRef.current = setInterval(fetchData, refreshInterval * 1000)
    }
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [fetchData, refreshInterval])

  return { data, loading, error, refetch: fetchData }
}

export async function postApi(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    if (res.status === 401) throw new Error('Please sign in to make picks')
    throw new Error(`HTTP ${res.status}`)
  }
  return res.json()
}
