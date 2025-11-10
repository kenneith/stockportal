
import React, { useState, useMemo, useEffect, useRef } from 'react'

const PAGE_TYPES = [
  { value: 'drawing_note', label: '圖說 / 明細表' },
  { value: 'plan', label: '平面圖' },
  { value: 'elevation', label: '立面圖' },
]

const DEFAULT_SETTINGS = {
  vlm_provider: 'stub',
  openai_api_key: '',
  openai_vlm_model: 'gpt-4.1-mini',
  neo4j_uri: '',
  neo4j_user: '',
  neo4j_password: '',
  pdf_dpi: 200,
}

const emptyReport = {
  majorBeams: [],
  minorBeams: [],
  columns: [],
}

function App() {
  const [session, setSession] = useState(null)
  const [pages, setPages] = useState([])
  const [currentPage, setCurrentPage] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [rotation, setRotation] = useState(0)
  const [uploading, setUploading] = useState(false)

  // 預覽互動狀態：拖曳 / 框選 + 平移 & 範圍
  const [interactionMode, setInteractionMode] = useState('pan') // 'pan' | 'select'
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const panStateRef = useRef({ startX: 0, startY: 0, originX: 0, originY: 0 })
  const [isPanning, setIsPanning] = useState(false)

  const [regions, setRegions] = useState([])
  const [drawingRegion, setDrawingRegion] = useState(null)
  const previewRef = useRef(null)

  const [pageMeta, setPageMeta] = useState({})
  const [analyzing, setAnalyzing] = useState(false)
  const [analyzeResult, setAnalyzeResult] = useState(null)

  const [activeTab, setActiveTab] = useState('pages') // 'pages' | 'report'

  // settings
  const [settings, setSettings] = useState(DEFAULT_SETTINGS)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsSaving, setSettingsSaving] = useState(false)

  // assistant chat
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [assistantSize, setAssistantSize] = useState('small') // 'small' | 'medium' | 'large'
  const [assistantMessages, setAssistantMessages] = useState([
    {
      role: 'assistant',
      content: '嗨，我是結構圖智能助理，有需要幫忙解讀圖面或估料設定可以直接問我！',
    },
  ])
  const [assistantInput, setAssistantInput] = useState('')
  const [assistantLoading, setAssistantLoading] = useState(false)

  // report data
  const [reportData, setReportData] = useState(emptyReport)
  const [reportSaving, setReportSaving] = useState(false)

  const currentIndex = useMemo(() => {
    if (!currentPage) return null
    return pages.indexOf(currentPage)
  }, [currentPage, pages])

  const currentMeta = currentPage ? pageMeta[currentPage] || {} : {}

  const normalizeRegion = (region) => {
    if (!region) return region
    let { x, y, width, height, id } = region
    if (width < 0) {
      x = x + width
      width = Math.abs(width)
    }
    if (height < 0) {
      y = y + height
      height = Math.abs(height)
    }
    return { id, x, y, width, height }
  }

  const handlePreviewMouseDown = (e) => {
    if (!currentPage) return
    const rect = e.currentTarget.getBoundingClientRect()
    const x = (e.clientX - rect.left) / zoom
    const y = (e.clientY - rect.top) / zoom

    if (interactionMode === 'pan') {
      setIsPanning(true)
      panStateRef.current = {
        startX: e.clientX,
        startY: e.clientY,
        originX: pan.x,
        originY: pan.y,
      }
    } else if (interactionMode === 'select') {
      const id = `${Date.now()}_${Math.random().toString(36).slice(2, 6)}`
      setDrawingRegion({
        id,
        x,
        y,
        width: 0,
        height: 0,
      })
    }
  }

  const handlePreviewMouseMove = (e) => {
    if (!currentPage) return
    if (interactionMode === 'pan') {
      if (!isPanning) return
      const { startX, startY, originX, originY } = panStateRef.current
      const dx = e.clientX - startX
      const dy = e.clientY - startY
      setPan({ x: originX + dx, y: originY + dy })
    } else if (interactionMode === 'select') {
      if (!drawingRegion) return
      const rect = e.currentTarget.getBoundingClientRect()
      const x = (e.clientX - rect.left) / zoom
      const y = (e.clientY - rect.top) / zoom
      setDrawingRegion((prev) => (prev ? { ...prev, width: x - prev.x, height: y - prev.y } : prev))
    }
  }

  const handlePreviewMouseUp = () => {
    if (!currentPage) return
    if (interactionMode === 'pan') {
      setIsPanning(false)
    } else if (interactionMode === 'select') {
      if (!drawingRegion) return
      const normalized = normalizeRegion(drawingRegion)
      if (normalized.width > 5 && normalized.height > 5) {
        setRegions((prev) => [...prev, normalized])
      }
      setDrawingRegion(null)
    }
  }

  
  useEffect(() => {
    // 初次載入時抓取後端設定
    const fetchSettings = async () => {
      try {
        const res = await fetch('/api/settings')
        if (!res.ok) throw new Error('settings fetch failed')
        const data = await res.json()
        setSettings({ ...DEFAULT_SETTINGS, ...data })
      } catch (err) {
        console.warn('讀取設定失敗，改用預設值。', err)
      }
    }
    fetchSettings()
  }, [])

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    setUploading(true)
    setAnalyzeResult(null)
    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) throw new Error('上傳失敗')
      const data = await res.json()
      setSession(data.session_id)
      setPages(data.pages)
      setCurrentPage(data.pages[0] || null)
      setPageMeta({})
      setReportData(emptyReport)
    } catch (err) {
      console.error(err)
      alert('上傳或處理檔案時發生錯誤，請稍後再試。')
    } finally {
      setUploading(false)
    }
  }

  const handleLoadSample = async () => {
    setUploading(true)
    setAnalyzeResult(null)
    try {
      const res = await fetch('/api/sample/c4')
      if (!res.ok) throw new Error('載入範例失敗')
      const data = await res.json()
      setSession(data.session_id)
      setPages(data.pages || [])
      setCurrentPage((data.pages && data.pages[0]) || null)
      setPageMeta({})
      setReportData(emptyReport)
    } catch (err) {
      console.error(err)
      alert('載入範例圖紙時發生錯誤')
    } finally {
      setUploading(false)
    }
  }

  const handleZoom = (delta) => {
    setZoom((z) => Math.min(3, Math.max(0.3, z + delta)))
  }

  const handleRotate = () => {
    setRotation((r) => (r + 90) % 360)
  }


  // 使用 addEventListener 註冊 wheel 事件，避免 passive listener 限制
  useEffect(() => {
    const el = previewRef.current
    if (!el) return

    const handleWheel = (e) => {
      // 允許阻止預設滾動行為
      e.preventDefault()
      if (!currentPage) return
      const delta = e.deltaY
      if (delta === 0) return
      const step = delta > 0 ? -0.1 : 0.1
      handleZoom(step)
    }

    el.addEventListener('wheel', handleWheel, { passive: false })

    return () => {
      el.removeEventListener('wheel', handleWheel)
    }
  }, [currentPage, handleZoom])

  const updateCurrentMeta = (partial) => {
    if (!currentPage) return
    setPageMeta((prev) => ({
      ...prev,
      [currentPage]: {
        ...(prev[currentPage] || {}),
        ...partial,
      },
    }))
  }

  const handleAnalyze = async () => {
    if (!session || currentIndex === null || currentIndex < 0) {
      alert('尚未選擇頁面或 session 無效')
      return
    }
    const pageType = currentMeta.pageType || null
    const prompt = (currentMeta.prompt || '').trim()
    if (!pageType) {
      alert('請先選擇頁面類型')
      return
    }
    if (!prompt) {
      alert('請先輸入或調整 Prompt 內容')
      return
    }
    setAnalyzing(true)
    setAnalyzeResult(null)
    try {
      const res = await fetch(`/api/sessions/${session}/pages/${currentIndex}/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          page_type: pageType,
          prompt,
        }),
      })
      if (!res.ok) throw new Error('解析失敗')
      const data = await res.json()
      setAnalyzeResult(data)
    } catch (err) {
      console.error(err)
      alert('呼叫解析 API 時發生錯誤')
    } finally {
      setAnalyzing(false)
    }
  }

  const handleAutoPrompt = (type) => {
    let base = ''
    if (type === 'drawing_note') {
      base =
        '你是一位鋼構工程圖專家，請在此圖說 / 明細表中，解析出桿件名稱、編號、層別、STEEL斷面尺寸、RC斷面尺寸、備註，輸出為結構化 JSON。'
    } else if (type === 'plan') {
      base =
        '你是一位鋼構工程圖專家，請在此平面圖中解析：樓層、斷面尺寸表（類別、編號）、坐標系、柱表、大梁表、小梁表，並輸出為結構化 JSON。'
    } else if (type === 'elevation') {
      base =
        '你是一位鋼構工程圖專家，請在此立面圖中解析：切面、坐標系、樓層高程、桿件表（編號、節次、所在座標系、長度粗估），並輸出為結構化 JSON。'
    }
    if (!currentMeta.prompt || currentMeta.prompt.trim() === '') {
      updateCurrentMeta({ prompt: base })
    }
  }

    const handleSaveSettings = async () => {
  setSettingsSaving(true);
  try {
    const res = await fetch('/api/settings', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings)
    });
    if (!res.ok) throw new Error('設定儲存失敗');
    const data = await res.json();
    setSettings({ ...DEFAULT_SETTINGS, ...data });
    setSettingsOpen(false);
  } catch (err) {
    console.error(err);
    alert('儲存設定時發生錯誤');
  } finally {
    setSettingsSaving(false);
  }
}


// ===== VLM 解析結果整理工具 =====

  const extractVlmItems = (parsed) => {
    if (!parsed) return []
    // 直接是陣列的情況
    if (Array.isArray(parsed)) return parsed
    // 常見 key: items / members / elements 等
    for (const key of ['items', 'members', 'elements', '構件清單']) {
      if (Array.isArray(parsed[key])) return parsed[key]
    }
    // 退一步：找第一個是陣列的欄位
    for (const key of Object.keys(parsed)) {
      if (Array.isArray(parsed[key])) return parsed[key]
    }
    return []
  }

  const mapVlmItemToReportRow = (item) => {
    if (!item || typeof item !== 'object') {
      return { id: Date.now(), name: '', spec: '', length: 0, quantity: 0, weight: 0 }
    }
    const getter = (...keys) => {
      for (const k of keys) {
        if (item[k] !== undefined && item[k] !== null && item[k] !== '') return item[k]
      }
      return ''
    }

    const name = getter('member_name', 'name', '桿件名稱', '構件名稱')
    const spec = getter(
      'steel_section',
      'section',
      'spec',
      '規格',
      '斷面尺寸',
      'STEEL斷面尺寸',
      '型號',
    )
    const lengthRaw = getter('length', '長度', '長度_m')
    const quantityRaw = getter('quantity', 'count', '數量')
    const weightRaw = getter('weight', '重量_t', '重量')

    const toNumber = (v) => {
      if (typeof v === 'number') return v
      if (typeof v === 'string') {
        const cleaned = v.replace(/[^0-9.+-]/g, '')
        const num = Number(cleaned)
        return Number.isFinite(num) ? num : 0
      }
      return 0
    }

    return {
      id: `${Date.now()}-${Math.random()}`,
      name: name || '',
      spec: spec || '',
      length: toNumber(lengthRaw),
      quantity: toNumber(quantityRaw) || 0,
      weight: toNumber(weightRaw),
    }
  }

  const classifyVlmItem = (item) => {
    if (!item || typeof item !== 'object') return 'majorBeams'
    const getter = (...keys) => {
      for (const k of keys) {
        if (item[k] !== undefined && item[k] !== null && item[k] !== '') return String(item[k])
      }
      return ''
    }
    const typeStr = getter('type', 'category', 'kind', '構件分類', '類別').toLowerCase()
    if (/柱|column/.test(typeStr)) return 'columns'
    if (/小梁|minor/.test(typeStr)) return 'minorBeams'
    if (/大梁|主梁|major/.test(typeStr)) return 'majorBeams'
    // 也可以用名稱判斷
    const nameStr = getter('member_name', 'name', '桿件名稱', '構件名稱').toLowerCase()
    if (/柱|column/.test(nameStr)) return 'columns'
    if (/小梁|minor/.test(nameStr)) return 'minorBeams'
    if (/大梁|主梁|major/.test(nameStr)) return 'majorBeams'
    return 'majorBeams'
  }

  const renderAnalyzeSummary = (result) => {
    if (!result) return null
    const parsed = result.parsed_data || {}
    const items = extractVlmItems(parsed)
    if (!items.length) {
      return (
        <div className="text-xs text-slate-400 mb-2">
          目前尚未從 VLM 結果中偵測到構件清單，以下為完整 JSON 資料。
        </div>
      )
    }

    return (
      <div className="mb-2 border border-slate-700 rounded-lg overflow-hidden">
        <div className="px-2 py-1 bg-slate-900/80 text-xs text-slate-300">
          構件清單預覽（從 VLM 解析結果整理）
        </div>
        <div className="max-h-56 overflow-auto text-xs">
          <table className="min-w-full border-collapse">
            <thead>
              <tr className="bg-slate-900/80 text-slate-300">
                <th className="border border-slate-700 px-2 py-1">類別</th>
                <th className="border border-slate-700 px-2 py-1">構件名稱</th>
                <th className="border border-slate-700 px-2 py-1">規格/型號</th>
                <th className="border border-slate-700 px-2 py-1">長度</th>
                <th className="border border-slate-700 px-2 py-1">數量</th>
                <th className="border border-slate-700 px-2 py-1">重量</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => {
                const row = mapVlmItemToReportRow(item)
                const section = classifyVlmItem(item)
                return (
                  <tr key={idx} className="bg-slate-900/60 text-slate-100">
                    <td className="border border-slate-800 px-1.5 py-1 text-[11px]">
                      {section === 'majorBeams' ? '大梁' : section === 'minorBeams' ? '小梁' : '柱'}
                    </td>
                    <td className="border border-slate-800 px-1.5 py-1 text-[11px]">{row.name}</td>
                    <td className="border border-slate-800 px-1.5 py-1 text-[11px]">{row.spec}</td>
                    <td className="border border-slate-800 px-1.5 py-1 text-[11px] text-right">
                      {row.length || ''}
                    </td>
                    <td className="border border-slate-800 px-1.5 py-1 text-[11px] text-right">
                      {row.quantity || ''}
                    </td>
                    <td className="border border-slate-800 px-1.5 py-1 text-[11px] text-right">
                      {row.weight || ''}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    )
  }


  const toggleAssistant = () => {
    setAssistantOpen((v) => !v)
  }

  const handleAssistantSend = async () => {
    const content = assistantInput.trim()
    if (!content) return
    const sid = session || 'sample_c4'
    const newMessages = [...assistantMessages, { role: 'user', content }]
    setAssistantMessages(newMessages)
    setAssistantInput('')
    setAssistantLoading(true)
    try {
      const res = await fetch('/api/assistant/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sid,
          messages: newMessages,
        }),
      })
      if (!res.ok) throw new Error('assistant error')
      const data = await res.json()
      setAssistantMessages((msgs) => [...msgs, { role: 'assistant', content: data.answer || '' }])
    } catch (err) {
      console.error(err)
      setAssistantMessages((msgs) => [
        ...msgs,
        { role: 'assistant', content: '抱歉，呼叫智能助理時發生錯誤。' },
      ])
    } finally {
      setAssistantLoading(false)
    }
  }

  // ===== 報表相關 =====

  const updateReportItem = (section, index, field, value) => {
    setReportData((prev) => {
      const arr = [...prev[section]]
      const row = { ...arr[index], [field]: field === 'length' || field === 'quantity' || field === 'weight' ? Number(value) || 0 : value }
      arr[index] = row
      return { ...prev, [section]: arr }
    })
  }

  const addReportRow = (section) => {
    const base = { id: Date.now(), name: '', spec: '', length: 0, quantity: 0, weight: 0 }
    setReportData((prev) => ({
      ...prev,
      [section]: [...prev[section], base],
    }))
  }

  const removeReportRow = (section, index) => {
    setReportData((prev) => {
      const arr = [...prev[section]]
      arr.splice(index, 1)
      return { ...prev, [section]: arr }
    })
  }

  const calcTotals = (rows) => {
    return rows.reduce(
      (acc, r) => {
        acc.length += Number(r.length) || 0
        acc.quantity += Number(r.quantity) || 0
        acc.weight += Number(r.weight) || 0
        return acc
      },
      { length: 0, quantity: 0, weight: 0 },
    )
  }

  const handleSaveReportAndSyncGraph = async () => {
    if (!session) {
      alert('尚未有有效的 session，請先載入圖紙。')
      return
    }
    setReportSaving(true)
    try {
      const payload = {
        session_id: session,
        report: reportData,
      }
      const res = await fetch(`/api/sessions/${session}/report/graph-sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error('報表同步失敗')
      await res.json()
      alert('報表已儲存並嘗試同步至 Neo4j 圖譜。')
    } catch (err) {
      console.error(err)
      alert('報表儲存或同步時發生錯誤。')
    } finally {
      setReportSaving(false)
    }
  }



  const handleAutoFillReport = () => {
    if (!session) {
      alert('尚未有有效的 session，請先載入圖紙。')
      return
    }
    const pages = Object.values(vlmResults || {})
    if (!pages.length) {
      alert('目前尚未有任何 VLM 解析結果，請先在「圖面解析」頁面執行單頁解析。')
      return
    }

    const nextReport = {
      majorBeams: [],
      minorBeams: [],
      columns: [],
    }

    pages.forEach((res) => {
      if (!res || !res.parsed_data) return
      const items = extractVlmItems(res.parsed_data)
      items.forEach((item) => {
        const section = classifyVlmItem(item)
        const row = mapVlmItemToReportRow(item)
        nextReport[section].push(row)
      })
    })

    if (
      nextReport.majorBeams.length === 0 &&
      nextReport.minorBeams.length === 0 &&
      nextReport.columns.length === 0
    ) {
      alert('VLM 解析結果中沒有找到可整理的構件資料（預期為陣列列表）。')
      return
    }

    setReportData(nextReport)
    setActiveTab('report')
    alert('已根據目前的 VLM 解析結果整理出估料報表草稿，請再人工檢查與修正。')
  }

  const handleExportReport = async () => {
    if (!session) {
      alert('尚未有有效的 session，請先載入圖紙。')
      return
    }
    try {
      const payload = {
        session_id: session,
        report: reportData,
      }
      const res = await fetch(`/api/sessions/${session}/report/export-excel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (!res.ok) {
        const text = await res.text()
        throw new Error(text || '匯出報表失敗')
      }
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      const ts = new Date().toISOString().slice(0, 10).replace(/-/g, '')
      a.href = url
      a.download = `估料報表_${session || ''}_${ts}.xlsx`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error(err)
      alert('匯出報表時發生錯誤，請確認後端是否已安裝 openpyxl 並重新啟動。')
    }
  }

  const renderReportTable = (title, sectionKey) => {
    const rows = reportData[sectionKey]
    const totals = calcTotals(rows)
    return (
      <div className="mb-4 rounded-xl border border-slate-700 bg-slate-950/60">
        <div className="px-3 py-2 flex items-center justify-between border-b border-slate-800">
          <div className="text-sm font-semibold text-slate-200">{title}</div>
          <button
            onClick={() => addReportRow(sectionKey)}
            className="px-2 py-1 rounded-md text-sm border border-slate-600 bg-slate-800 hover:border-brand-400 hover:text-brand-100"
            type="button"
          >
            新增列
          </button>
        </div>
        <div className="overflow-x-auto text-sm">
          <table className="min-w-full border-collapse">
            <thead>
              <tr className="bg-slate-900/80 text-slate-300">
                <th className="border border-slate-700 px-2 py-1">構件名稱</th>
                <th className="border border-slate-700 px-2 py-1">規格/型號</th>
                <th className="border border-slate-700 px-2 py-1">長度 (m)</th>
                <th className="border border-slate-700 px-2 py-1">數量</th>
                <th className="border border-slate-700 px-2 py-1">重量 (t)</th>
                <th className="border border-slate-700 px-2 py-1">操作</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, idx) => (
                <tr key={r.id || idx} className="bg-slate-900/60">
                  <td className="border border-slate-800 px-1.5 py-1">
                    <input
                      className="w-full bg-transparent outline-none text-slate-100"
                      value={r.name}
                      onChange={(e) => updateReportItem(sectionKey, idx, 'name', e.target.value)}
                    />
                  </td>
                  <td className="border border-slate-800 px-1.5 py-1">
                    <input
                      className="w-full bg-transparent outline-none text-slate-100"
                      value={r.spec}
                      onChange={(e) => updateReportItem(sectionKey, idx, 'spec', e.target.value)}
                    />
                  </td>
                  <td className="border border-slate-800 px-1.5 py-1 text-right">
                    <input
                      type="number"
                      className="w-full bg-transparent outline-none text-right"
                      value={r.length}
                      onChange={(e) => updateReportItem(sectionKey, idx, 'length', e.target.value)}
                    />
                  </td>
                  <td className="border border-slate-800 px-1.5 py-1 text-right">
                    <input
                      type="number"
                      className="w-full bg-transparent outline-none text-right"
                      value={r.quantity}
                      onChange={(e) => updateReportItem(sectionKey, idx, 'quantity', e.target.value)}
                    />
                  </td>
                  <td className="border border-slate-800 px-1.5 py-1 text-right">
                    <input
                      type="number"
                      className="w-full bg-transparent outline-none text-right"
                      value={r.weight}
                      onChange={(e) => updateReportItem(sectionKey, idx, 'weight', e.target.value)}
                    />
                  </td>
                  <td className="border border-slate-800 px-1.5 py-1 text-center">
                    <button
                      type="button"
                      className="text-red-400 hover:text-red-300"
                      onClick={() => removeReportRow(sectionKey, idx)}
                    >
                      刪除
                    </button>
                  </td>
                </tr>
              ))}
              <tr className="bg-slate-900/80 font-semibold text-slate-200">
                <td className="border border-slate-800 px-1.5 py-1 text-right" colSpan={2}>
                  小計
                </td>
                <td className="border border-slate-800 px-1.5 py-1 text-right">
                  {totals.length.toFixed(3)}
                </td>
                <td className="border border-slate-800 px-1.5 py-1 text-right">
                  {totals.quantity}
                </td>
                <td className="border border-slate-800 px-1.5 py-1 text-right">
                  {totals.weight.toFixed(3)}
                </td>
                <td className="border border-slate-800 px-1.5 py-1" />
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-sm font-bold text-white">
            SS
          </div>
          <div>
            <div className="font-semibold tracking-wide">Steel Structure VLM Material Integrator</div>
            <div className="text-sm text-slate-400">圖紙 VLM 解析 · 材料整合 · Tekla 匯出 · Neo4j 圖譜</div>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <label className="relative inline-flex items-center px-4 py-1.5 rounded-full bg-gradient-to-r from-brand-600 to-brand-700 border border-brand-500 cursor-pointer text-sm shadow-md shadow-brand-900/40">
            <span className="mr-2 text-white">
              {uploading ? '處理中…' : '上傳圖紙 (PDF/PNG)'}
            </span>
            <input
              type="file"
              accept=".pdf,image/png,image/jpeg"
              className="absolute inset-0 opacity-0 cursor-pointer"
              onChange={handleFileChange}
              disabled={uploading}
            />
          </label>
          <button
            type="button"
            onClick={handleLoadSample}
            className="px-3 py-1.5 rounded-full border border-slate-600 bg-slate-800/80 text-sm text-slate-100 hover:border-brand-400 hover:text-brand-100 hover:bg-slate-700/90 transition"
          >
            載入範例圖紙
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="px-3 py-1.5 rounded-full border border-slate-700 bg-slate-900/80 text-sm text-slate-200 hover:border-brand-500 hover:text-brand-100 hover:bg-slate-800/80 transition"
          >
            參數設定
          </button>
          {session && (
            <span className="text-sm text-slate-500">
              Session:{' '}
              <span className="font-mono bg-slate-800/70 px-2 py-0.5 rounded-md text-slate-200">
                {session.slice(0, 8)}...
              </span>
            </span>
          )}
        </div>
      </header>

      {/* Tab bar */}
      <div className="border-b border-slate-800 bg-slate-950/80 px-6 pt-2">
        <div className="flex gap-4 text-sm">
          <button
            className={`pb-2 border-b-2 ${
              activeTab === 'pages'
                ? 'border-brand-500 text-brand-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
            onClick={() => setActiveTab('pages')}
          >
            圖面解析
          </button>
          <button
            className={`pb-2 border-b-2 ${
              activeTab === 'report'
                ? 'border-brand-500 text-brand-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
            onClick={() => setActiveTab('report')}
          >
            估料報表
          </button>
        </div>
      </div>

      {activeTab === 'pages' ? (
        <main className="flex-1 grid grid-cols-[260px_minmax(0,1.6fr)_minmax(0,1.3fr)] gap-0">
          {/* Left - Page list */}
          <aside className="border-r border-slate-800 bg-slate-900/60 backdrop-blur p-3 flex flex-col">
            <div className="text-sm font-semibold text-slate-400 mb-2">頁面列表</div>
            <div className="flex-1 overflow-y-auto space-y-1">
              {pages.length === 0 && (
                <div className="text-sm text-slate-500 mt-4">
                  請先上傳 PDF 或圖檔，或點擊右上方「載入範例圖紙」。
                </div>
              )}
              {pages.map((p, idx) => (
                <button
                  key={p}
                  onClick={() => {
                    setCurrentPage(p)
                    setAnalyzeResult(null)
                  }}
                  className={`w-full text-left px-3 py-2 rounded-lg text-sm border transition ${
                    currentPage === p
                      ? 'border-brand-500 bg-brand-600/80 text-white shadow-md shadow-brand-900/40'
                      : 'border-slate-800 bg-slate-900/80 hover:border-brand-500 hover:bg-slate-800/80 text-slate-200'
                  }`}
                >
                  <div className="font-medium">Page {idx + 1}</div>
                  <div className="text-[10px] text-slate-400 truncate">{p}</div>
                </button>
              ))}
            </div>
          </aside>

          {/* Center - Viewer */}
          <section className="border-r border-slate-800 bg-slate-900/40 flex flex-col">
            <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
              <div className="text-sm font-semibold text-slate-400">
                圖面預覽 {currentIndex !== null && currentIndex >= 0 ? `(Page ${currentIndex + 1})` : ''}
              </div>
              <div className="flex items-center gap-2 text-sm">
                <button
                  onClick={() => handleZoom(-0.1)}
                  className="px-2 py-1 rounded-md border border-slate-700 bg-slate-800 text-slate-100 hover:bg-brand-600 hover:border-brand-400 hover:text-white transition"
                >
                  -
                </button>
                <span className="w-14 text-center">{Math.round(zoom * 100)}%</span>
                <button
                  onClick={() => handleZoom(0.1)}
                  className="px-2 py-1 rounded-md border border-slate-700 bg-slate-800 text-slate-100 hover:bg-brand-600 hover:border-brand-400 hover:text-white transition"
                >
                  +
                </button>
                <button
                  onClick={handleRotate}
                  className="ml-3 px-2 py-1 rounded-md border border-slate-700 bg-slate-800 text-slate-100 hover:bg-brand-600 hover:border-brand-400 hover:text-white transition"
                >
                  旋轉 90°
                </button>
                <button
                  onClick={() => {
                    setZoom(1)
                    setRotation(0)
                    setPan({ x: 0, y: 0 })
                  }}
                  className="ml-1 px-2 py-1 rounded-md border border-slate-700 bg-slate-800 text-slate-100 hover:bg-brand-600 hover:border-brand-400 hover:text-white transition"
                >
                  重設
                </button>
                <div className="ml-3 flex items-center gap-1">
                  <span className="text-sm text-slate-400 mr-1">操作模式</span>
                  <button
                    className={`px-2 py-1 rounded-md border text-sm ${
                      interactionMode === 'pan'
                        ? 'border-brand-500 text-brand-300 bg-slate-900'
                        : 'border-slate-700 text-slate-400 hover:text-slate-100'
                    }`}
                    onClick={() => setInteractionMode('pan')}
                  >
                    拖曳
                  </button>
                  <button
                    className={`px-2 py-1 rounded-md border text-sm ${
                      interactionMode === 'select'
                        ? 'border-brand-500 text-brand-300 bg-slate-900'
                        : 'border-slate-700 text-slate-400 hover:text-slate-100'
                    }`}
                    onClick={() => setInteractionMode('select')}
                  >
                    框選
                  </button>
                  <button
                    className="ml-1 px-2 py-1 rounded-md border border-slate-700 text-sm text-slate-400 hover:text-slate-100 hover:border-brand-400"
                    onClick={() => {
                      setRegions([])
                      setDrawingRegion(null)
                    }}
                  >
                    清除範圍
                  </button>
                </div>
              </div>
            </div>
            <div className="flex-1 overflow-auto flex items-center justify-center bg-slate-950/60">
              {currentPage ? (
                <div
                  ref={previewRef}
                  className="relative"
                  onMouseDown={handlePreviewMouseDown}
                  onMouseMove={handlePreviewMouseMove}
                  onMouseUp={handlePreviewMouseUp}
                  style={{
                    transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom}) rotate(${rotation}deg)`,
                    transformOrigin: 'center center',
                    transition: 'transform 0.12s ease-out',
                    cursor: interactionMode === 'pan' ? 'grab' : 'crosshair',
                  }}
                >
                  <img
                    src={currentPage}
                    className="shadow-2xl max-w-none select-none pointer-events-none"
                  />
                  {regions.map((r) => (
                    <div
                      key={r.id}
                      className="pointer-events-none absolute border-2 border-emerald-300/90 shadow-[0_0_0_1px_rgba(15,23,42,0.9)] bg-emerald-400/5"
                      style={{
                        left: r.x,
                        top: r.y,
                        width: r.width,
                        height: r.height,
                      }}
                    />
                  ))}
                  {drawingRegion && (
                    <div
                      className="pointer-events-none absolute border-2 border-indigo-300/90 border-dashed bg-indigo-400/5"
                      style={{
                        left: normalizeRegion(drawingRegion).x,
                        top: normalizeRegion(drawingRegion).y,
                        width: Math.abs(drawingRegion.width),
                        height: Math.abs(drawingRegion.height),
                      }}
                    />
                  )}
                </div>
              ) : (
                <div className="text-sm text-slate-500">尚未選擇頁面。</div>
              )}
            </div>
          </section>

          {/* Right - Page type, prompt, analyze result */}
          <aside className="bg-slate-900/60 p-4 flex flex-col border-l border-slate-800/60">
            <div className="text-sm font-semibold text-slate-400 mb-2">單頁解析設定與結果</div>

            {!currentPage || currentIndex === null ? (
              <div className="flex-1 rounded-xl border border-dashed border-slate-700 bg-slate-950/40 p-4 text-sm text-slate-400">
                請從左側選擇一個頁面，設定類型與 Prompt 後，即可進行 VLM 單頁解析，並同步更新 Neo4j 知識圖譜。
              </div>
            ) : (
              <>
                <div className="mb-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex-1">
                      <label className="block text-sm text-slate-400 mb-1">頁面類型</label>
                      <select
                        className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:border-brand-500"
                        value={currentMeta.pageType || ''}
                        onChange={(e) => {
                          const value = e.target.value || null
                          updateCurrentMeta({ pageType: value })
                          if (value) handleAutoPrompt(value)
                        }}
                      >
                        <option value="">請選擇類型</option>
                        {PAGE_TYPES.map((t) => (
                          <option key={t.value} value={t.value}>
                            {t.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="text-sm text-slate-500">
                      Page{' '}
                      <span className="font-mono bg-slate-800/70 px-1.5 py-0.5 rounded">
                        {currentIndex + 1}
                      </span>
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm text-slate-400 mb-1">
                      Prompt 內容（可依頁面調整）
                    </label>
                    <textarea
                      rows={6}
                      className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:border-brand-500 resize-none text-slate-100"
                      value={currentMeta.prompt || ''}
                      onChange={(e) => updateCurrentMeta({ prompt: e.target.value })}
                      placeholder="請輸入此頁的解析指令（Prompt）…"
                    />
                  </div>

                  <div className="flex items-center justify-between">
                    <div className="text-sm text-slate-500">
                      解析狀態：{' '}
                      {analyzing ? (
                        <span className="text-brand-400">解析中…</span>
                      ) : analyzeResult ? (
                        <span className="text-emerald-400">已取得結果並已嘗試寫入圖譜</span>
                      ) : (
                        <span className="text-slate-500">尚未解析</span>
                      )}
                    </div>
                    <button
                      onClick={handleAnalyze}
                      disabled={analyzing}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm font-medium bg-gradient-to-r from-brand-500 to-brand-700 hover:from-brand-400 hover:to-brand-600 disabled:opacity-60 disabled:cursor-not-allowed shadow-md shadow-brand-900/40 text-white"
                    >
                      {analyzing ? '解析中…' : '執行單頁解析'}
                    </button>
                  </div>
                </div>

                <div className="flex-1 rounded-xl border border-slate-700 bg-slate-950/60 p-3 text-sm overflow-auto">
                  <div className="flex items-center justify-between mb-1">
                    <div className="text-sm text-slate-400">
                      VLM 解析結果（依設定可能為 stub 或 OpenAI）
                    </div>
                  </div>
                  {analyzeResult ? (
                    <>
                      {renderAnalyzeSummary(analyzeResult)}
                      <details className="mt-2">
                        <summary className="text-xs text-slate-400 cursor-pointer hover:text-slate-200">
                          檢視完整 JSON 結果
                        </summary>
                        <pre className="mt-1 font-mono text-xs leading-snug text-slate-200 whitespace-pre-wrap">
                          {JSON.stringify(analyzeResult, null, 2)}
                        </pre>
                      </details>
                    </>
                  ) : (
                    <div className="text-xs text-slate-500">// 尚未解析或尚無結果</div>
                  )}
                </div>
              </>
            )}
          </aside>
        </main>
      ) : (
        // 報表 Tab
        <main className="flex-1 bg-slate-950/80 px-6 py-4">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm font-semibold text-slate-100">估料報表</div>
              <div className="text-sm text-slate-400">
                依「大梁 / 小梁 / 柱」分頁呈現，可手動編輯與新增。可先由 VLM 結果自動整理，再同步至圖譜或匯出 Excel。
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleAutoFillReport}
                className="px-3 py-1.5 rounded-lg text-sm border border-slate-600 text-slate-100 bg-slate-900 hover:border-brand-400 hover:text-brand-100"
              >
                整理估料報表
              </button>
              <button
                type="button"
                onClick={handleSaveReportAndSyncGraph}
                disabled={reportSaving}
                className="px-4 py-1.5 rounded-lg text-sm bg-gradient-to-r from-brand-500 to-brand-700 text-white hover:from-brand-400 hover:to-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {reportSaving ? '同步中…' : '儲存並同步圖譜'}
              </button>
              <button
                type="button"
                onClick={handleExportReport}
                className="px-3 py-1.5 rounded-lg text-sm border border-slate-600 text-slate-100 bg-slate-900 hover:border-brand-400 hover:text-brand-100"
              >
                輸出報表
              </button>
            </div>
ent-to-r from-brand-500 to-brand-700 text-white hover:from-brand-400 hover:to-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {reportSaving ? '同步中…' : '儲存並同步圖譜'}
            </button>
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            <div>
              {renderReportTable('大梁彙總表', 'majorBeams')}
              {renderReportTable('小梁彙總表', 'minorBeams')}
            </div>
            <div>
              {renderReportTable('柱彙總表', 'columns')}
            </div>
          </div>
        </main>
      )}

      {/* 參數設定 Modal */}
      {settingsOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-30">
          <div className="w-full max-w-xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-semibold text-slate-100">參數設定</div>
              <button
                onClick={() => setSettingsOpen(false)}
                className="text-sm text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3 text-sm">
              <div>
                <label className="block text-sm text-slate-400 mb-1">VLM Provider</label>
                <select
                  className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm"
                  value={settings.vlm_provider}
                  onChange={(e) => setSettings((s) => ({ ...s, vlm_provider: e.target.value }))}
                >
                  <option value="stub">stub（僅示意，不打外部 API）</option>
                  <option value="openai">OpenAI</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-slate-400 mb-1">OpenAI API Key</label>
                <input
                  type="password"
                  className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm"
                  value={settings.openai_api_key}
                  onChange={(e) => setSettings((s) => ({ ...s, openai_api_key: e.target.value }))}
                  placeholder="sk-..."
                />
              </div>

              <div>
                <label className="block text-sm text-slate-400 mb-1">OpenAI VLM Model</label>
                <select
                  className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm"
                  value={settings.openai_vlm_model || 'gpt-4.1-mini'}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, openai_vlm_model: e.target.value }))
                  }
                >
                  <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                  <option value="gpt-4.1">gpt-4.1</option>
                  <option value="gpt-4o-mini">gpt-4o-mini</option>
                  <option value="gpt-4o">gpt-4o</option>
                </select>
              </div>
              <div className="border-t border-slate-800 pt-2 mt-1">
                <div className="text-sm text-slate-400 mb-1">Neo4j 連線設定</div>
                <div className="space-y-2">
                  <div>
                    <label className="block text-sm text-slate-400 mb-1">URI</label>
                    <input
                      type="text"
                      className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm"
                      value={settings.neo4j_uri}
                      onChange={(e) => setSettings((s) => ({ ...s, neo4j_uri: e.target.value }))}
                      placeholder="bolt://localhost:7687"
                    />
                  </div>
                  <div className="flex gap-2">
                    <div className="flex-1">
                      <label className="block text-sm text-slate-400 mb-1">User</label>
                      <input
                        type="text"
                        className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm"
                        value={settings.neo4j_user}
                        onChange={(e) =>
                          setSettings((s) => ({ ...s, neo4j_user: e.target.value }))
                        }
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm text-slate-400 mb-1">Password</label>
                      <input
                        type="password"
                        className="w-full bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm"
                        value={settings.neo4j_password}
                        onChange={(e) =>
                          setSettings((s) => ({ ...s, neo4j_password: e.target.value }))
                        }
                      />
                    </div>
                  </div>
                </div>
              </div>
              <div className="border-t border-slate-800 pt-2 mt-1">
                <label className="block text-sm text-slate-400 mb-1">PDF 轉圖解析度 (DPI)</label>
                <input
                  type="number"
                  className="w-32 bg-slate-950/60 border border-slate-700 rounded-lg px-2 py-1.5 text-sm"
                  value={settings.pdf_dpi}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, pdf_dpi: Number(e.target.value) || 150 }))
                  }
                  min={72}
                  max={600}
                />
              </div>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => setSettingsOpen(false)}
                className="px-3 py-1.5 rounded-lg text-sm border border-slate-700 bg-slate-900/80 text-slate-200 hover:bg-slate-800/80"
              >
                取消
              </button>
              <button
                onClick={handleSaveSettings}
                disabled={settingsSaving}
                className="px-3 py-1.5 rounded-lg text-sm bg-gradient-to-r from-brand-500 to-brand-700 text-white hover:from-brand-400 hover:to-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {settingsSaving ? '儲存中…' : '儲存設定'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 智能助理懸浮按鈕與對話框 */}
      <div className="fixed bottom-4 right-4 z-40">
        {assistantOpen && (
          <div
            className={`mb-3 rounded-2xl border border-slate-700 bg-slate-900/95 shadow-2xl flex flex-col ${
              assistantSize === 'small'
                ? 'w-[320px] h-[360px]'
                : assistantSize === 'medium'
                  ? 'w-[420px] h-[480px]'
                  : 'w-[90vw] h-[80vh]'
            }`}
          >
            <div className="px-3 py-2 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
              <img
                src="/assistant-avatar.png"
                alt="虛擬助理頭像"
                className="w-7 h-7 rounded-full border border-slate-500 object-cover"
              />
              <div className="text-sm font-semibold text-slate-100">智能助理</div>
            </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1">
                  <button
                    className={`px-1.5 py-0.5 rounded text-sm border ${
                      assistantSize === 'small'
                        ? 'border-brand-500 text-brand-300 bg-slate-900'
                        : 'border-slate-700 text-slate-400 hover:text-slate-100'
                    }`}
                    onClick={() => setAssistantSize('small')}
                  >
                    小
                  </button>
                  <button
                    className={`px-1.5 py-0.5 rounded text-sm border ${
                      assistantSize === 'medium'
                        ? 'border-brand-500 text-brand-300 bg-slate-900'
                        : 'border-slate-700 text-slate-400 hover:text-slate-100'
                    }`}
                    onClick={() => setAssistantSize('medium')}
                  >
                    中
                  </button>
                  <button
                    className={`px-1.5 py-0.5 rounded text-sm border ${
                      assistantSize === 'large'
                        ? 'border-brand-500 text-brand-300 bg-slate-900'
                        : 'border-slate-700 text-slate-400 hover:text-slate-100'
                    }`}
                    onClick={() => setAssistantSize('large')}
                  >
                    大
                  </button>
                </div>
                <button
                  className="text-sm text-slate-400 hover:text-slate-100"
                  onClick={() => setAssistantOpen(false)}
                >
                  ✕
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto px-3 py-2 space-y-2 text-sm">
              {assistantMessages.length === 0 && (
                <div className="text-slate-500">
                  你可以詢問：例如「這個建物的大梁型號有哪些？」、「哪幾支柱長度超過 10 公尺？」等。
                </div>
              )}
              {assistantMessages.map((m, idx) => (
                <div
                  key={idx}
                  className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[80%] rounded-xl px-3 py-1.5 whitespace-pre-wrap ${
                      m.role === 'user'
                        ? 'bg-brand-600 text-white'
                        : 'bg-slate-800 text-slate-100 border border-slate-700'
                    }`}
                  >
                    {m.content}
                  </div>
                </div>
              ))}
              {assistantLoading && (
                <div className="text-sm text-slate-400">助理思考中…</div>
              )}
            </div>
            <div className="border-t border-slate-800 px-3 py-2 flex items-center gap-2">
              <input
                type="text"
                className="flex-1 bg-slate-950/70 border border-slate-700 rounded-lg px-2 py-1.5 text-sm text-slate-100 focus:outline-none focus:border-brand-500"
                placeholder="輸入問題…"
                value={assistantInput}
                onChange={(e) => setAssistantInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleAssistantSend()
                  }
                }}
              />
              <button
                onClick={handleAssistantSend}
                disabled={assistantLoading}
                className="px-3 py-1.5 rounded-lg text-sm bg-gradient-to-r from-brand-500 to-brand-700 text-white hover:from-brand-400 hover:to-brand-600 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                發送
              </button>
            </div>
          </div>
        )}

        <button
          className="w-12 h-12 rounded-full bg-gradient-to-br from-brand-500 to-brand-700 shadow-lg shadow-brand-900/50 flex items-center justify-center text-xl"
          onClick={toggleAssistant}
        >
          💬
        </button>
      </div>
    </div>
  )
}

export default App
