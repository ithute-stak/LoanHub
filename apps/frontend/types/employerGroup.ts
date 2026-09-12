export type EmployerGroup = {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type EmployerGroupCreate = {
  code: string;
  name: string;
};
