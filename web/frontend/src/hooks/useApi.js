import { useState, useEffect, useRef } from 'react'
import axios from 'axios'

export function useApi(url) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const abortRef = useRef(null)

  useEffect(() => {
    if (!url) {
      setLoading(false)
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

    axios.get(url, { signal: controller.signal })
      .then(res => {
        setData(res.data)
        setLoading(false)
      })
      .catch(err => {
        if (!axios.isCancel(err)) {
          setError(err.message)
          setLoading(false)
        }
      })

    return () => controller.abort()
  }, [url])

  return { data, loading, error }
}
