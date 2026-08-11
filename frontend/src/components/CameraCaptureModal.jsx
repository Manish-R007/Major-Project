import { useEffect, useRef, useState } from 'react'

export default function CameraCaptureModal({ onCapture, onClose }) {
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [error, setError] = useState('')

  useEffect(() => {
    async function startCamera() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } },
          audio: false,
        })
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      } catch {
        setError('Camera access was blocked or is unavailable. Allow camera permission, then try again.')
      }
    }
    startCamera()
    return () => streamRef.current?.getTracks().forEach((track) => track.stop())
  }, [])

  function capture() {
    const video = videoRef.current
    if (!video?.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    canvas.toBlob((blob) => {
      if (!blob) return
      onCapture(new File([blob], `fra-document-${Date.now()}.jpg`, { type: 'image/jpeg' }))
    }, 'image/jpeg', 0.92)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/75 p-4">
      <div className="w-full max-w-2xl rounded-2xl bg-parchment-100 p-5 shadow-2xl">
        <div className="flex items-center justify-between gap-4">
          <div><h2 className="font-display text-xl text-canopy-950">Scan claim document</h2><p className="text-xs text-canopy-700/60">Fit the full page inside the camera frame, then capture.</p></div>
          <button onClick={onClose} className="rounded-full px-3 py-1 text-sm text-canopy-800 hover:bg-parchment-200">Close</button>
        </div>
        <div className="mt-4 overflow-hidden rounded-xl bg-black"><video ref={videoRef} autoPlay playsInline className="max-h-[65vh] w-full object-contain" /></div>
        {error && <p className="mt-3 text-sm text-rust-600">{error}</p>}
        <div className="mt-4 flex justify-end gap-3">
          <button onClick={onClose} className="rounded-lg border border-canopy-900/20 px-4 py-2 text-sm text-canopy-900">Cancel</button>
          <button onClick={capture} disabled={!!error} className="rounded-lg bg-ochre-500 px-5 py-2 text-sm font-medium text-canopy-950 disabled:opacity-50">Capture and upload</button>
        </div>
      </div>
    </div>
  )
}
