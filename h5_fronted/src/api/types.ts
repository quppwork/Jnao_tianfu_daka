/** 测试类型 */
export type TestType = "孩子" | "成人";

// ========== JNAO Report Types ==========

export interface JnaoAttributeItem {
  id: string;
  name: string;
  value: number;
  grade: number;
}

export interface JnaoAttribute {
  attribute: JnaoAttributeItem;
  attributeList: JnaoAttributeItem[];
  desp: string;
  SupplementDesp: string | null;
}

export interface JnaoState {
  name: string;
  id: number;
  desp: string;
}

export interface JnaoTalent {
  abilityName: string;
  abilityID: string;
  grade: number;
  value: number;
  desp: string;
}

export interface JnaoAbility {
  abilityName: string;
  abilityID: string;
  grade: number;
  value: number;
  desp: string;
}

export interface JnaoTalentType {
  id: string;
  name: string;
  desp: string;
}

export interface JnaoReportResults {
  Attribute: JnaoAttribute;
  State: JnaoState;
  Talent: JnaoTalent;
  TalentType: JnaoTalentType[];
  Ability: JnaoAbility[];
}

export interface JnaoReportData {
  id: number;
  uid: number;
  type: number;
  talent: string;
  check_talent: string;
  create_time: string;
  results: JnaoReportResults;
  property: string;
  AttributeJs: string;
  StateIcon: string;
}

