import React, { useState, useEffect, useRef } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000/api";

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard'); // dashboard, review, audit
  const [theme, setTheme] = useState(() => {
    return localStorage.getItem('theme') || 'dark';
  });

  const [metrics, setMetrics] = useState({
    scope1_co2e_kg: 0,
    scope2_co2e_kg: 0,
    scope3_co2e_kg: 0,
    total_co2e_kg: 0,
    total_records: 0,
    pending_records: 0,
    approved_records: 0,
    locked_records: 0,
    suspicious_records: 0
  });
  const [timeline, setTimeline] = useState([]);
  const [recentJobs, setRecentJobs] = useState([]);
  const [categoryBreakdown, setCategoryBreakdown] = useState([]);
  
  // Review Table state
  const [records, setRecords] = useState([]);
  const [filterScope, setFilterScope] = useState('');
  const [filterSource, setFilterSource] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterSuspicious, setFilterSuspicious] = useState('');
  const [selectedRowIds, setSelectedRowIds] = useState([]);
  const [expandedRowId, setExpandedRowId] = useState(null);

  // Edit Modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingRecord, setEditingRecord] = useState(null);
  const [editQty, setEditQty] = useState('');
  const [editCategory, setEditCategory] = useState('');
  const [editStartDate, setEditStartDate] = useState('');
  const [editEndDate, setEditEndDate] = useState('');
  const [editSuspiciousFlag, setEditSuspiciousFlag] = useState(false);
  const [editSuspiciousReason, setEditSuspiciousReason] = useState('');

  // Ingestion Ingest Form state
  const [ingestSourceType, setIngestSourceType] = useState('SAP');
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState(null);
  const fileInputRef = useRef(null);

  // Audit Logs state
  const [auditLogs, setAuditLogs] = useState([]);

  useEffect(() => {
    fetchDashboardMetrics();
    fetchRecords();
    fetchAuditTrail();
  }, []);

  // Theme Sync hook
  useEffect(() => {
    if (theme === 'light') {
      document.body.classList.add('light-theme');
    } else {
      document.body.classList.remove('light-theme');
    }
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'dark' ? 'light' : 'dark');
  };

  const fetchDashboardMetrics = async () => {
    try {
      const res = await fetch(`${API_BASE}/metrics/`);
      const data = await res.json();
      if (data.metrics) setMetrics(data.metrics);
      if (data.emissions_timeline) setTimeline(data.emissions_timeline);
      if (data.recent_jobs) setRecentJobs(data.recent_jobs);
      if (data.category_breakdown) setCategoryBreakdown(data.category_breakdown);
    } catch (e) {
      console.error("Error fetching metrics:", e);
    }
  };

  const fetchRecords = async () => {
    try {
      let url = `${API_BASE}/records/`;
      const params = [];
      if (filterScope) params.push(`scope=${filterScope}`);
      if (filterSource) params.push(`source_type=${filterSource}`);
      if (filterStatus) params.push(`status=${filterStatus}`);
      if (filterSuspicious) params.push(`suspicious=${filterSuspicious}`);
      if (params.length) url += `?${params.join('&')}`;

      const res = await fetch(url);
      const data = await res.json();
      setRecords(data);
    } catch (e) {
      console.error("Error fetching records:", e);
    }
  };

  const fetchAuditTrail = async () => {
    try {
      const res = await fetch(`${API_BASE}/audit-trail/`);
      const data = await res.json();
      setAuditLogs(data);
    } catch (e) {
      console.error("Error fetching audit trail:", e);
    }
  };

  useEffect(() => {
    fetchRecords();
  }, [filterScope, filterSource, filterStatus, filterSuspicious]);

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      setUploadMessage({ type: 'error', text: 'Please select a file to upload.' });
      return;
    }

    setUploadLoading(true);
    setUploadMessage(null);

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('source_type', ingestSourceType);

    try {
      const res = await fetch(`${API_BASE}/ingest/`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      
      if (res.ok) {
        setUploadMessage({ type: 'success', text: data.message });
        setUploadFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
        
        fetchDashboardMetrics();
        fetchRecords();
        fetchAuditTrail();
      } else {
        setUploadMessage({ type: 'error', text: data.error || 'Failed to ingest data.' });
      }
    } catch (err) {
      setUploadMessage({ type: 'error', text: 'Error connecting to the backend server.' });
    } finally {
      setUploadLoading(false);
    }
  };

  // Bulk Actions
  const handleBulkApprove = async () => {
    if (!selectedRowIds.length) return;
    try {
      const res = await fetch(`${API_BASE}/records/bulk-approve/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_ids: selectedRowIds })
      });
      setSelectedRowIds([]);
      fetchDashboardMetrics();
      fetchRecords();
      fetchAuditTrail();
    } catch (e) {
      console.error(e);
    }
  };

  const handleBulkLock = async () => {
    if (!selectedRowIds.length) return;
    try {
      const res = await fetch(`${API_BASE}/records/bulk-lock/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ record_ids: selectedRowIds })
      });
      setSelectedRowIds([]);
      fetchDashboardMetrics();
      fetchRecords();
      fetchAuditTrail();
    } catch (e) {
      console.error(e);
    }
  };

  // Row selection helpers
  const toggleSelectRow = (id, e) => {
    e.stopPropagation();
    if (selectedRowIds.includes(id)) {
      setSelectedRowIds(selectedRowIds.filter(x => x !== id));
    } else {
      setSelectedRowIds([...selectedRowIds, id]);
    }
  };

  const toggleSelectAll = () => {
    if (selectedRowIds.length === records.length) {
      setSelectedRowIds([]);
    } else {
      setSelectedRowIds(records.filter(r => !r.is_locked).map(r => r.id));
    }
  };

  const openEditModal = (rec, e) => {
    e.stopPropagation();
    setEditingRecord(rec);
    setEditQty(rec.normalized_quantity);
    setEditCategory(rec.category);
    setEditStartDate(rec.start_date || '');
    setEditEndDate(rec.end_date || '');
    setEditSuspiciousFlag(rec.suspicious_flag);
    setEditSuspiciousReason(rec.suspicious_reason || '');
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = async () => {
    try {
      const res = await fetch(`${API_BASE}/records/${editingRecord.id}/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          normalized_quantity: editQty,
          category: editCategory,
          start_date: editStartDate,
          end_date: editEndDate,
          suspicious_flag: editSuspiciousFlag,
          suspicious_reason: editSuspiciousReason
        })
      });
      if (res.ok) {
        setIsEditModalOpen(false);
        setEditingRecord(null);
        fetchDashboardMetrics();
        fetchRecords();
        fetchAuditTrail();
      } else {
        const err = await res.json();
        alert(err.error || "Failed to update record");
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Visual SVG chart distributions
  const scopeTotals = [
    { name: 'Scope 1', value: metrics.scope1_co2e_kg, color: 'var(--scope1)' },
    { name: 'Scope 2', value: metrics.scope2_co2e_kg, color: 'var(--scope2)' },
    { name: 'Scope 3', value: metrics.scope3_co2e_kg, color: 'var(--scope3)' }
  ];
  
  const totalValue = scopeTotals.reduce((a, b) => a + b.value, 0);

  return (
    <div className="app-container">
      {/* App Header */}
      <header className="app-header">
        <div className="logo-section">
          <div className="logo-glow"></div>
          <h1>Breathe ESG</h1>
        </div>
        <div className="header-right">
          <nav className="nav-tabs">
            <button 
              className={`tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`}
              onClick={() => setActiveTab('dashboard')}
            >
              Dashboard
            </button>
            <button 
              className={`tab-btn ${activeTab === 'review' ? 'active' : ''}`}
              onClick={() => setActiveTab('review')}
            >
              Audit Review
            </button>
            <button 
              className={`tab-btn ${activeTab === 'audit' ? 'active' : ''}`}
              onClick={() => setActiveTab('audit')}
            >
              Audit Trail
            </button>
          </nav>
          <button onClick={toggleTheme} className="theme-toggle-btn" aria-label="Toggle Theme" style={{display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '8px', borderRadius: '50%', width: '36px', height: '36px'}}>
            {theme === 'dark' ? (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="4"/>
                <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
              </svg>
            ) : (
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
              </svg>
            )}
          </button>
        </div>
      </header>

      {/* Main Content Areas */}
      {activeTab === 'dashboard' && (
        <>
          {/* Metrics summary grid */}
          <div className="dashboard-grid">
            <div className="metric-card scope1">
              <div className="metric-label">Scope 1 (Direct Fuel)</div>
              <div className="metric-value">{(metrics.scope1_co2e_kg).toLocaleString(undefined, {maximumFractionDigits: 1})}</div>
              <div className="metric-unit">kg CO₂e</div>
              <div className="metric-sub">
                <span>Direct stationary combustion</span>
              </div>
            </div>
            <div className="metric-card scope2">
              <div className="metric-label">Scope 2 (Electricity)</div>
              <div className="metric-value">{(metrics.scope2_co2e_kg).toLocaleString(undefined, {maximumFractionDigits: 1})}</div>
              <div className="metric-unit">kg CO₂e</div>
              <div className="metric-sub">
                <span>Indirect energy from local grids</span>
              </div>
            </div>
            <div className="metric-card scope3">
              <div className="metric-label">Scope 3 (Travel)</div>
              <div className="metric-value">{(metrics.scope3_co2e_kg).toLocaleString(undefined, {maximumFractionDigits: 1})}</div>
              <div className="metric-unit">kg CO₂e</div>
              <div className="metric-sub">
                <span>Indirect corporate travel logs</span>
              </div>
            </div>
            <div className="metric-card total">
              <div className="metric-label">Total Normalised Carbon</div>
              <div className="metric-value">{(metrics.total_co2e_kg).toLocaleString(undefined, {maximumFractionDigits: 1})}</div>
              <div className="metric-unit">kg CO₂e</div>
              <div className="metric-sub">
                <span>Records: {metrics.total_records}</span>
                <span>Flagged: {metrics.suspicious_records}</span>
              </div>
            </div>
          </div>

          <div className="panel-grid">
            {/* Custom SVG Bar Chart */}
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title">Emissions Timeline Trends</h3>
              </div>
              <div className="chart-container">
                {timeline.length === 0 ? (
                  <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: 'var(--text-muted)', fontSize: '13px'}}>
                    No ingested activity logs available. Upload a file to see emissions timeline.
                  </div>
                ) : (
                  <svg className="chart-svg" viewBox="0 0 500 200">
                    <line x1="40" y1="20" x2="480" y2="20" stroke="var(--border-color)" strokeWidth="1" />
                    <line x1="40" y1="75" x2="480" y2="75" stroke="var(--border-color)" strokeWidth="1" />
                    <line x1="40" y1="130" x2="480" y2="130" stroke="var(--border-color)" strokeWidth="1" />
                    <line x1="40" y1="165" x2="480" y2="165" stroke="var(--text-muted)" strokeWidth="1" opacity="0.3" />
                    
                    {timeline.map((item, idx) => {
                      const maxVal = Math.max(...timeline.map(t => t.total), 100);
                      const barWidth = 35;
                      const gap = 30;
                      const startX = 60 + idx * (barWidth + gap);
                      
                      const hScope1 = (item['Scope 1'] / maxVal) * 135;
                      const hScope2 = (item['Scope 2'] / maxVal) * 135;
                      const hScope3 = (item['Scope 3'] / maxVal) * 135;
                      
                      const y3 = 165 - hScope3;
                      const y2 = y3 - hScope2;
                      const y1 = y2 - hScope1;

                      return (
                        <g key={idx}>
                          {hScope3 > 0 && <rect className="bar-rect" x={startX} y={y3} width={barWidth} height={hScope3} fill="var(--scope3)" rx="2" />}
                          {hScope2 > 0 && <rect className="bar-rect" x={startX} y={y2} width={barWidth} height={hScope2} fill="var(--scope2)" rx="2" />}
                          {hScope1 > 0 && <rect className="bar-rect" x={startX} y={y1} width={barWidth} height={hScope1} fill="var(--scope1)" rx="2" />}
                          
                          <text x={startX + barWidth/2} y="185" fill="var(--text-muted)" fontSize="9" textAnchor="middle">
                            {item.month}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                )}
              </div>
            </div>

            {/* Custom Donut chart */}
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title">Emissions Share</h3>
              </div>
              <div style={{display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center'}}>
                <div style={{width: '120px', height: '120px', position: 'relative'}}>
                  <svg width="100%" height="100%" viewBox="0 0 42 42">
                    <circle cx="21" cy="21" r="15.915" fill="transparent" stroke="var(--border-color)" strokeWidth="4"></circle>
                    {totalValue > 0 && (() => {
                      let accumulatedPercent = 0;
                      return scopeTotals.map((item, idx) => {
                        const percent = (item.value / totalValue) * 100;
                        if (percent === 0) return null;
                        const dashArray = `${percent} ${100 - percent}`;
                        const dashOffset = 100 - accumulatedPercent + 25;
                        accumulatedPercent += percent;
                        return (
                          <circle 
                            key={idx}
                            cx="21" cy="21" r="15.915" 
                            fill="transparent" 
                            stroke={item.color} 
                            strokeWidth="4" 
                            strokeDasharray={dashArray} 
                            strokeDashoffset={dashOffset}
                          />
                        );
                      });
                    })()}
                  </svg>
                  <div style={{position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center'}}>
                    <span style={{fontSize: '10px', color: 'var(--text-muted)', textTransform: 'uppercase', display: 'block'}}>Total</span>
                    <div style={{fontSize: '14px', fontWeight: 'bold'}}>{(totalValue/1000).toFixed(1)}t</div>
                  </div>
                </div>
                
                <div style={{width: '100%', display: 'flex', flexDirection: 'column', gap: '6px'}}>
                  {scopeTotals.map((item, idx) => (
                    <div key={idx} style={{display: 'flex', justifyContent: 'space-between', fontSize: '12px', alignItems: 'center'}}>
                      <div style={{display: 'flex', alignItems: 'center', gap: '6px'}}>
                        <span style={{width: '8px', height: '8px', borderRadius: '50%', background: item.color}}></span>
                        <span>{item.name}</span>
                      </div>
                      <span style={{fontWeight: 'bold'}}>
                        {totalValue > 0 ? ((item.value / totalValue) * 100).toFixed(1) : 0}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Ingestion Panels */}
          <div className="panel-grid ingest-grid">
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title">Data Ingest Center</h3>
              </div>
              <form onSubmit={handleFileUpload} className="dropzone-container">
                <div className="source-selector">
                  <div 
                    className={`source-option ${ingestSourceType === 'SAP' ? 'selected' : ''}`}
                    onClick={() => setIngestSourceType('SAP')}
                  >
                    <div className="source-title">SAP CSV</div>
                    <div className="source-desc">Direct fuels</div>
                  </div>
                  <div 
                    className={`source-option ${ingestSourceType === 'UTILITY' ? 'selected' : ''}`}
                    onClick={() => setIngestSourceType('UTILITY')}
                  >
                    <div className="source-title">Utility CSV</div>
                    <div className="source-desc">Grid energy</div>
                  </div>
                  <div 
                    className={`source-option ${ingestSourceType === 'TRAVEL' ? 'selected' : ''}`}
                    onClick={() => setIngestSourceType('TRAVEL')}
                  >
                    <div className="source-title">Travel JSON</div>
                    <div className="source-desc">Travel API logs</div>
                  </div>
                </div>

                <div 
                  className="dropzone"
                  onClick={() => fileInputRef.current.click()}
                >
                  {uploadFile ? (
                    <div>
                      <strong style={{color: 'var(--primary)'}}>{uploadFile.name}</strong>
                      <p style={{fontSize: '11px', marginTop: '2px'}}>
                        ({(uploadFile.size / 1024).toFixed(1)} KB)
                      </p>
                    </div>
                  ) : (
                    <div>
                      <strong>Choose raw data file</strong>
                      <p>
                        Upload {ingestSourceType === 'TRAVEL' ? '.json' : '.csv'} file
                      </p>
                    </div>
                  )}
                  <input 
                    type="file" 
                    ref={fileInputRef}
                    className="file-input"
                    accept={ingestSourceType === 'TRAVEL' ? '.json' : '.csv'}
                    onChange={(e) => setUploadFile(e.target.files[0])}
                  />
                </div>

                <button 
                  type="submit" 
                  className="btn" 
                  disabled={uploadLoading || !uploadFile}
                  style={{width: '100%'}}
                >
                  {uploadLoading ? 'Parsing and Normalizing...' : 'Ingest and Process'}
                </button>

                {uploadMessage && (
                  <div style={{
                    padding: '10px', 
                    borderRadius: '6px', 
                    fontSize: '12px', 
                    textAlign: 'center',
                    background: uploadMessage.type === 'success' ? 'rgba(16, 185, 129, 0.08)' : 'rgba(239, 68, 68, 0.08)',
                    color: uploadMessage.type === 'success' ? 'var(--success)' : 'var(--danger)',
                    border: `1px solid ${uploadMessage.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)'}`
                  }}>
                    {uploadMessage.text}
                  </div>
                )}
              </form>
            </div>

            {/* Ingestion Queue panel */}
            <div className="panel">
              <div className="panel-header">
                <h3 className="panel-title">Processing Job History</h3>
              </div>
              <div className="table-container" style={{maxHeight: '260px'}}>
                <table className="data-table compact-table">
                  <thead>
                    <tr>
                      <th>Filename</th>
                      <th>Source Type</th>
                      <th>Processed At</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentJobs.length === 0 ? (
                      <tr>
                        <td colSpan="4" style={{textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', padding: '20px'}}>No processing jobs logged yet.</td>
                      </tr>
                    ) : (
                      recentJobs.map((job) => (
                        <tr key={job.id}>
                          <td>{job.file_name}</td>
                          <td><span className={`badge ${job.source_type.toLowerCase()}`}>{job.source_type}</span></td>
                          <td>{job.created_at}</td>
                          <td>
                            <span style={{
                              color: job.status === 'SUCCESS' ? 'var(--success)' : 'var(--danger)',
                              fontWeight: 'bold',
                              fontSize: '11px'
                            }}>
                              {job.status}
                            </span>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'review' && (
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Carbon Audit Review Grid</h3>
            {selectedRowIds.length > 0 && (
              <div style={{display: 'flex', gap: '8px'}}>
                <button className="btn" onClick={handleBulkApprove}>
                  Approve Selected ({selectedRowIds.length})
                </button>
                <button className="btn btn-secondary" onClick={handleBulkLock}>
                  Lock Selected for Audit
                </button>
              </div>
            )}
          </div>

          {/* Filter row controls */}
          <div className="filter-row">
            <div className="filters-group">
              <select className="select-control" value={filterScope} onChange={e => setFilterScope(e.target.value)}>
                <option value="">All Scopes</option>
                <option value="Scope 1">Scope 1 (Direct)</option>
                <option value="Scope 2">Scope 2 (Indirect)</option>
                <option value="Scope 3">Scope 3 (Travel)</option>
              </select>

              <select className="select-control" value={filterSource} onChange={e => setFilterSource(e.target.value)}>
                <option value="">All Ingestion Sources</option>
                <option value="SAP">SAP ERP (CSV)</option>
                <option value="UTILITY">Utility Portal (CSV)</option>
                <option value="TRAVEL">Concur Travel (JSON)</option>
              </select>

              <select className="select-control" value={filterStatus} onChange={e => setFilterStatus(e.target.value)}>
                <option value="">All Review Statuses</option>
                <option value="PENDING_REVIEW">Pending Review</option>
                <option value="APPROVED">Approved</option>
                <option value="LOCKED_FOR_AUDIT">Locked for Audit</option>
              </select>

              <select className="select-control" value={filterSuspicious} onChange={e => setFilterSuspicious(e.target.value)}>
                <option value="">Sanity Check Filter</option>
                <option value="true">Outliers / Suspicious</option>
                <option value="false">Standard Records</option>
              </select>
            </div>
            <div style={{fontSize: '12px', color: 'var(--text-muted)'}}>
              Showing {records.length} records
            </div>
          </div>

          {/* Data table review */}
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th width="40">
                    <input 
                      type="checkbox" 
                      checked={records.length > 0 && selectedRowIds.length === records.filter(r => !r.is_locked).length}
                      onChange={toggleSelectAll}
                    />
                  </th>
                  <th>Source</th>
                  <th>Scope</th>
                  <th>Activity / Category</th>
                  <th>Normalised Qty</th>
                  <th>Carbon Emissions</th>
                  <th>Dates Covered</th>
                  <th>Status</th>
                  <th>Flags</th>
                  <th width="60"></th>
                </tr>
              </thead>
              <tbody>
                {records.length === 0 ? (
                  <tr>
                    <td colSpan="10" style={{textAlign: 'center', color: 'var(--text-muted)', padding: '30px'}}>
                      No matching records found. Upload a file or adjust filters.
                    </td>
                  </tr>
                ) : (
                  records.map((rec) => {
                    const isExpanded = expandedRowId === rec.id;
                    const isSelected = selectedRowIds.includes(rec.id);
                    
                    return (
                      <React.Fragment key={rec.id}>
                        <tr 
                          className={rec.suspicious_flag ? 'suspicious-row' : ''}
                          onClick={() => setExpandedRowId(isExpanded ? null : rec.id)}
                        >
                          <td onClick={e => e.stopPropagation()}>
                            {!rec.is_locked && (
                              <input 
                                type="checkbox" 
                                checked={isSelected}
                                onChange={(e) => toggleSelectRow(rec.id, e)}
                              />
                            )}
                          </td>
                          <td>
                            <span className={`badge ${rec.source_type.toLowerCase()}`}>
                              {rec.source_type}
                            </span>
                          </td>
                          <td>
                            <span style={{
                              fontWeight: 'bold',
                              color: rec.scope === 'Scope 1' ? 'var(--scope1)' : rec.scope === 'Scope 2' ? 'var(--scope2)' : 'var(--scope3)'
                            }}>{rec.scope}</span>
                          </td>
                          <td>{rec.category}</td>
                          <td>
                            {rec.normalized_quantity.toLocaleString(undefined, {maximumFractionDigits: 2})}{' '}
                            <span style={{color: 'var(--text-muted)', fontSize: '10px'}}>{rec.normalized_unit}</span>
                          </td>
                          <td style={{fontWeight: '700'}}>
                            {rec.co2e_kg.toLocaleString(undefined, {maximumFractionDigits: 1})}{' '}
                            <span style={{color: 'var(--text-muted)', fontWeight: 'normal', fontSize: '10px'}}>kg CO₂e</span>
                          </td>
                          <td style={{fontSize: '11px'}}>
                            {rec.start_date} {rec.end_date !== rec.start_date && `to ${rec.end_date}`}
                          </td>
                          <td>
                            <span className={`badge ${rec.status.toLowerCase()}`}>
                              {rec.status.replace(/_/g, ' ')}
                            </span>
                          </td>
                          <td>
                            {rec.suspicious_flag ? (
                              <span className="badge suspicious" title={rec.suspicious_reason}>Outlier</span>
                            ) : (
                              <span style={{color: 'var(--success)'}}>Clear</span>
                            )}
                          </td>
                          <td onClick={e => e.stopPropagation()}>
                            {!rec.is_locked && (
                              <button 
                                className="btn btn-secondary" 
                                style={{padding: '4px 8px', fontSize: '11px'}}
                                onClick={(e) => openEditModal(rec, e)}
                              >
                                Edit
                              </button>
                            )}
                          </td>
                        </tr>

                        {/* Collapsible raw data view */}
                        {isExpanded && (
                          <tr>
                            <td colSpan="10" style={{background: 'rgba(0,0,0,0.03)', padding: '0'}}>
                              <div className="detail-drawer">
                                <div className="drawer-half">
                                  <div className="drawer-title">Exact Raw Payload (Unalterable Source of Truth)</div>
                                  <pre className="raw-json-block">
                                    {JSON.stringify(rec.raw_data, null, 2)}
                                  </pre>
                                </div>
                                
                                <div className="drawer-half">
                                  <div className="drawer-title">Emissions Calculation Formula</div>
                                  <div className="calculation-steps">
                                    <div className="calc-row">
                                      <span>Raw Quantity Input:</span>
                                      <strong style={{color: 'var(--text-main)'}}>{rec.raw_quantity.toLocaleString()} {rec.raw_unit}</strong>
                                    </div>
                                    <div className="calc-row">
                                      <span>Normalised Quantity:</span>
                                      <strong style={{color: 'var(--text-main)'}}>{rec.normalized_quantity.toLocaleString()} {rec.normalized_unit}</strong>
                                    </div>
                                    <div className="calc-row">
                                      <span>Activity Category:</span>
                                      <strong>{rec.category}</strong>
                                    </div>
                                    <div className="calc-row">
                                      <span>Emissions Factor Ratio:</span>
                                      <strong>{(rec.co2e_kg / (rec.normalized_quantity || 1)).toFixed(4)}</strong>
                                    </div>
                                    <div className="calc-row highlight">
                                      <span>Final Carbon:</span>
                                      <span>{rec.co2e_kg.toLocaleString(undefined, {maximumFractionDigits: 1})} kg CO₂e</span>
                                    </div>
                                    
                                    {rec.suspicious_flag && (
                                      <div style={{
                                        marginTop: '10px', 
                                        padding: '10px', 
                                        borderRadius: '6px', 
                                        background: 'rgba(239, 68, 68, 0.05)', 
                                        border: '1px solid rgba(239, 68, 68, 0.1)',
                                        fontSize: '11px'
                                      }}>
                                        <strong style={{color: 'var(--danger)', display: 'block', marginBottom: '2px'}}>Auditing Alert Flag:</strong>
                                        <span style={{color: 'var(--text-main)'}}>{rec.suspicious_reason}</span>
                                      </div>
                                    )}

                                    {rec.approved_by && (
                                      <div style={{
                                        marginTop: '10px', 
                                        padding: '6px 10px', 
                                        borderRadius: '6px', 
                                        background: 'rgba(16, 185, 129, 0.04)', 
                                        fontSize: '11px',
                                        color: 'var(--success)',
                                        display: 'flex',
                                        justifyContent: 'space-between'
                                      }}>
                                        <span>Verified By: <strong>{rec.approved_by}</strong></span>
                                        <span>{rec.approved_at}</span>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activeTab === 'audit' && (
        <div className="panel">
          <div className="panel-header">
            <h3 className="panel-title">Compliance Audit Trail</h3>
          </div>
          <div className="timeline">
            {auditLogs.length === 0 ? (
              <div style={{textAlign: 'center', padding: '30px', color: 'var(--text-muted)', fontSize: '13px'}}>
                No compliance operations logged yet. Modify a record or approve it to trigger logs.
              </div>
            ) : (
              auditLogs.map((log) => (
                <div key={log.id} className="timeline-item">
                  <div className="timeline-marker">
                    <div className="timeline-dot"></div>
                    <div className="timeline-line"></div>
                  </div>
                  <div className="timeline-content">
                    <div className="timeline-meta">
                      <span>Timestamp: <strong>{log.timestamp}</strong></span>
                      <span>Operator: <strong style={{color: 'var(--primary)'}}>{log.user}</strong></span>
                    </div>
                    <div className="timeline-action">
                      <span className={`badge ${log.source_type.toLowerCase()}`} style={{marginRight: '6px'}}>
                        {log.source_type}
                      </span>
                      <span>
                        Action <strong>{log.action}</strong> on record ID #{log.record_id}
                      </span>
                    </div>
                    <div style={{fontSize: '12px', marginBottom: '6px', color: 'var(--text-muted)'}}>
                      Category: {log.category}
                    </div>
                    {Object.keys(log.changes).length > 0 && (
                      <div className="timeline-changes">
                        {Object.entries(log.changes).map(([field, delta]) => (
                          <div key={field}>
                            {field}: <span style={{color: 'var(--danger)'}}>{JSON.stringify(delta.old)}</span> to <span style={{color: 'var(--success)'}}>{JSON.stringify(delta.new)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Manual record Editor Modal */}
      {isEditModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div className="modal-header">
              <h3>Correct Carbon Data</h3>
              <button 
                onClick={() => setIsEditModalOpen(false)}
                style={{background: 'transparent', border: 'none', color: 'var(--text-muted)', fontSize: '18px', cursor: 'pointer'}}
              >
                ✕
              </button>
            </div>
            
            <div className="form-group">
              <label className="form-label">Normalised Activity Quantity ({editingRecord.normalized_unit})</label>
              <input 
                type="number" 
                className="form-input" 
                value={editQty}
                onChange={e => setEditQty(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Emission Category</label>
              <input 
                type="text" 
                className="form-input" 
                value={editCategory}
                onChange={e => setEditCategory(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Activity Start Date</label>
              <input 
                type="date" 
                className="form-input" 
                value={editStartDate}
                onChange={e => setEditStartDate(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Activity End Date</label>
              <input 
                type="date" 
                className="form-input" 
                value={editEndDate}
                onChange={e => setEditEndDate(e.target.value)}
              />
            </div>

            <div className="form-group" style={{flexDirection: 'row', alignItems: 'center', gap: '8px'}}>
              <input 
                type="checkbox" 
                id="modal-suspicious"
                checked={editSuspiciousFlag}
                onChange={e => setEditSuspiciousFlag(e.target.checked)}
              />
              <label htmlFor="modal-suspicious" className="form-label" style={{cursor: 'pointer'}}>Flag as Suspicious</label>
            </div>

            {editSuspiciousFlag && (
              <div className="form-group">
                <label className="form-label">Reason for Flagging</label>
                <input 
                  type="text" 
                  className="form-input" 
                  value={editSuspiciousReason}
                  onChange={e => setEditSuspiciousReason(e.target.value)}
                  placeholder="Inconsistent metrics or manual adjustments"
                />
              </div>
            )}

            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setIsEditModalOpen(false)}>
                Cancel
              </button>
              <button className="btn" onClick={handleSaveEdit}>
                Recalculate and Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
