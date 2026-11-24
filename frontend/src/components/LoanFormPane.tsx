import React, { useState } from 'react';
import { Check, ClipboardList, Copy, Download, FileText, LayoutList } from 'lucide-react';
import { CompletionStats, LoanApplicationData } from '../types';

interface LoanFormPaneProps {
  application: LoanApplicationData;
  highlightedFields: Record<string, number>;
  completion: CompletionStats;
  plainTextDoc: string;
  sessionId: string | null;
  onEditField: (field: keyof LoanApplicationData, value: string) => void;
}

interface FieldSpec {
  key: keyof LoanApplicationData;
  label: string;
  placeholder: string;
  wide?: boolean;
}

interface FormSection {
  title: string;
  subtitle: string;
  fields: FieldSpec[];
}

const SECTIONS: FormSection[] = [
  {
    title: '1. Loan & Scheme Request',
    subtitle: 'BOI AG-100 · SBI KCC · Axis Kisan Power',
    fields: [
      { key: 'facility_type', label: 'Loan Facility Type', placeholder: 'e.g. Fresh KCC / Crop Loan / Term Loan' },
      { key: 'amount_required_inr', label: 'Amount Required (₹)', placeholder: 'e.g. 150000' },
      { key: 'loan_purpose', label: 'Purpose of Loan', placeholder: 'e.g. Wheat & paddy cultivation, seeds, dairy', wide: true },
    ],
  },
  {
    title: '2. Applicant Identity',
    subtitle: 'Personal & Literacy Accessibility',
    fields: [
      { key: 'full_name', label: 'Full Name', placeholder: 'Farmer full name' },
      { key: 'father_or_spouse_name', label: 'Father / Spouse Name', placeholder: 'S/o, D/o, W/o' },
      { key: 'age', label: 'Age / DOB', placeholder: 'e.g. 42' },
      { key: 'gender', label: 'Gender', placeholder: 'Male / Female / Other' },
      { key: 'mobile_number', label: 'Mobile Number', placeholder: '10-digit mobile' },
      { key: 'social_category', label: 'Social Category', placeholder: 'General / OBC / SC / ST' },
      { key: 'education_level', label: 'Education / Literacy', placeholder: 'e.g. Illiterate / Primary' },
      { key: 'requires_thumb_impression_lti', label: 'Thumb Impression (LTI)', placeholder: 'Yes / No' },
    ],
  },
  {
    title: '3. Address & Location',
    subtitle: 'Rural Residence Details',
    fields: [
      { key: 'village', label: 'Village', placeholder: 'Village name' },
      { key: 'post_office', label: 'Post Office', placeholder: 'Post office' },
      { key: 'taluka_mandal', label: 'Taluka / Mandal', placeholder: 'Tehsil / Block' },
      { key: 'district', label: 'District', placeholder: 'District name' },
      { key: 'state', label: 'State', placeholder: 'State name' },
      { key: 'pin_code', label: 'PIN Code', placeholder: '6-digit PIN' },
    ],
  },
  {
    title: '4. Land, Crops & Allied Farming',
    subtitle: 'Cultivation, Livestock & Equipment',
    fields: [
      { key: 'land_title', label: 'Land Title', placeholder: 'Owned / Leased / Share Cropper' },
      { key: 'total_land_acres', label: 'Total Land Area', placeholder: 'e.g. 4 acres / 6 bigha' },
      { key: 'irrigated_acres', label: 'Irrigated Area', placeholder: 'e.g. 3 acres' },
      { key: 'irrigation_source', label: 'Irrigation Source', placeholder: 'Borewell / Canal / Drip / Rainfed' },
      { key: 'survey_khasra_no', label: 'Survey / Khasra No.', placeholder: 'Or "Field agent to verify"', wide: true },
      { key: 'kharif_crops', label: 'Kharif Crops', placeholder: 'e.g. Paddy, Cotton, Soybean' },
      { key: 'rabi_crops', label: 'Rabi Crops', placeholder: 'e.g. Wheat, Mustard, Gram' },
      { key: 'other_crops', label: 'Other / Horticulture', placeholder: 'Vegetables, Sugarcane, Fruits' },
      { key: 'allied_activities', label: 'Dairy / Livestock / Fish', placeholder: 'e.g. 3 buffaloes, 10 goats' },
      { key: 'farm_machinery', label: 'Farm Machinery Owned', placeholder: 'Tractor, Pumpset, Tiller', wide: true },
    ],
  },
  {
    title: '5. Banking, KYC & Income',
    subtitle: 'PM-KISAN & Existing Credit Profile',
    fields: [
      { key: 'pm_kisan_beneficiary', label: 'PM-KISAN Beneficiary', placeholder: 'Yes / No' },
      { key: 'existing_bank_name', label: 'Existing Bank & Branch', placeholder: 'e.g. SBI, Bank of India, RRB' },
      { key: 'has_savings_or_pmjdy_account', label: 'Savings / PMJDY A/c', placeholder: 'Yes / PMJDY / No' },
      { key: 'annual_agri_income_inr', label: 'Annual Farm Income (₹)', placeholder: 'e.g. 120000' },
      { key: 'annual_other_income_inr', label: 'Other Annual Income (₹)', placeholder: 'Non-farm / allied income' },
      { key: 'available_kyc_docs', label: 'Available KYC Docs', placeholder: 'Aadhaar, Voter ID, Passbook', wide: true },
      { key: 'existing_loans_summary', label: 'Existing Loans', placeholder: 'None, or outstanding details', wide: true },
    ],
  },
  {
    title: '6. Insurance & Field Agent Handoff',
    subtitle: 'Consent & Assisted Visit Notes',
    fields: [
      { key: 'pmfby_crop_insurance_consent', label: 'PMFBY Crop Insurance', placeholder: 'Yes / No / Needs Info' },
      { key: 'pmsby_pmjjby_consent', label: 'PMSBY / PMJJBY Cover', placeholder: 'Yes / No / Needs Info' },
      { key: 'preferred_language', label: 'Preferred Language', placeholder: 'e.g. Hindi, Tamil, Marathi' },
      { key: 'verbal_consent_for_agent_callback', label: 'Agent Visit Consent', placeholder: 'Yes / No' },
      { key: 'field_agent_visit_notes', label: 'Field Agent Visit Notes', placeholder: 'Preferred time, documents to verify...', wide: true },
    ],
  },
];

export const LoanFormPane: React.FC<LoanFormPaneProps> = ({
  application,
  highlightedFields,
  completion,
  plainTextDoc,
  sessionId,
  onEditField,
}) => {
  const [viewMode, setViewMode] = useState<'form' | 'text'>('form');
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(plainTextDoc);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // ignore
    }
  };

  const handleExportJson = () => {
    const blob = new Blob(
      [
        JSON.stringify(
          {
            session_id: sessionId || 'draft',
            exported_at: new Date().toISOString(),
            completion,
            application,
          },
          null,
          2
        ),
      ],
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `kisan-loan-application-${sessionId || 'draft'}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section className="flex flex-col h-full min-h-0 overflow-hidden bg-white min-w-0">
      {/* Header + Progress */}
      <div className="px-4 py-3 border-b border-[#ECEAE4] bg-white space-y-2.5">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <ClipboardList className="w-4 h-4 text-[#1B5E3F] shrink-0" />
            <h2 className="text-xs font-semibold uppercase tracking-wider text-[#46524B] truncate">
              Loan Application
            </h2>
            <span className="text-[11px] font-semibold text-[#1B5E3F] bg-[#EBF4EE] px-2 py-0.5 rounded-full">
              {completion.percent}%
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            {/* Toggle Form vs Live Text Field View */}
            <div className="inline-flex p-0.5 rounded-lg bg-[#F2F1EC] border border-[#E5E2DC]">
              <button
                type="button"
                onClick={() => setViewMode('form')}
                className={`p-1 rounded-md cursor-pointer transition-colors ${
                  viewMode === 'form' ? 'bg-white text-[#1B5E3F] shadow-2xs' : 'text-[#737E78]'
                }`}
                title="Live Structured Form Fields"
              >
                <LayoutList className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={() => setViewMode('text')}
                className={`p-1 rounded-md cursor-pointer transition-colors ${
                  viewMode === 'text' ? 'bg-white text-[#1B5E3F] shadow-2xs' : 'text-[#737E78]'
                }`}
                title="Live Text Document View"
              >
                <FileText className="w-3.5 h-3.5" />
              </button>
            </div>

            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg border border-[#E5E2DC] text-[11px] font-medium text-[#46524B] hover:bg-[#F5F4F0] cursor-pointer transition-colors"
              title="Copy Application Summary"
            >
              {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
              <span className="hidden xl:inline">{copied ? 'Copied' : 'Copy'}</span>
            </button>

            <button
              type="button"
              onClick={handleExportJson}
              className="inline-flex items-center gap-1 px-2 py-1 rounded-lg bg-[#1B5E3F] hover:bg-[#154C32] text-white text-[11px] font-medium cursor-pointer transition-colors"
              title="Export Application JSON for Field Agent"
            >
              <Download className="w-3 h-3" />
              <span className="hidden xl:inline">Export</span>
            </button>
          </div>
        </div>

        {/* Thin Progress Bar */}
        <div className="flex items-center gap-2.5">
          <div className="flex-1 h-1.5 rounded-full bg-[#EFECE6] overflow-hidden">
            <div
              className="h-full bg-[#1B5E3F] rounded-full transition-all duration-500"
              style={{ width: `${completion.percent}%` }}
            />
          </div>
          <span className="text-[11px] text-[#78827C] shrink-0">
            {completion.core_filled}/{completion.core_total} core fields
          </span>
        </div>
      </div>

      {/* Body: Live Structured Form Fields OR Unified Live Text Sheet */}
      {viewMode === 'text' ? (
        <div className="flex-1 p-4 overflow-hidden flex flex-col bg-[#FAF9F6]">
          <textarea
            readOnly
            value={plainTextDoc}
            className="flex-1 w-full resize-none rounded-xl border border-[#E5E2DC] bg-white p-4 font-mono text-[12px] leading-relaxed text-[#1E2A24] outline-none"
          />
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-5 bg-[#FCFCFA]">
          {SECTIONS.map((sec) => (
            <div
              key={sec.title}
              className="rounded-2xl border border-[#EAE8E2] bg-white p-3.5 shadow-[0_1px_2px_rgba(0,0,0,0.015)]"
            >
              <div className="mb-3 pb-2 border-b border-[#F2F0EB]">
                <h3 className="text-xs font-semibold text-[#1B3A2A]">{sec.title}</h3>
                <p className="text-[10.5px] text-[#838D87]">{sec.subtitle}</p>
              </div>
              <div className="grid grid-cols-2 gap-2.5">
                {sec.fields.map((f) => {
                  const val = application[f.key] ?? '';
                  const flashStamp = highlightedFields[f.key];
                  const isFilled = Boolean(val);
                  return (
                    <div key={f.key} className={f.wide ? 'col-span-2' : 'col-span-1'}>
                      <label className="block text-[10.5px] font-medium text-[#5E6A63] mb-1">
                        {f.label}
                      </label>
                      <input
                        key={`${f.key}-${flashStamp || 0}`}
                        type="text"
                        value={val}
                        onChange={(e) => onEditField(f.key, e.target.value)}
                        placeholder={f.placeholder}
                        className={`w-full rounded-lg border px-2.5 py-1.5 text-xs transition-colors outline-none ${
                          flashStamp ? 'animate-field-flash' : ''
                        } ${
                          isFilled
                            ? 'border-[#C5DACE] bg-[#F7FBF8] text-[#14261D] font-medium focus:border-[#1B5E3F]'
                            : 'border-[#E6E4DE] bg-white text-[#1C2420] placeholder:text-[#B3B9B5] focus:border-[#1B5E3F]'
                        }`}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
