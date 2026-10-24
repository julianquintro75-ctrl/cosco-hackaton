import { Routes } from '@angular/router';
import { guardia, rolGuardia } from './core/auth';

export const routes: Routes = [
  { path: 'login', title: 'Login', loadComponent: () => import('./pages/login').then(m => m.Login) },
  {
    path: '', canActivate: [guardia], loadComponent: () => import('./layout/shell').then(m => m.Shell),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'recomendar' },
      { path: 'nueva', loadComponent: () => import('./pages/nueva').then(m => m.Nueva) },
      { path: 'recomendar', loadComponent: () => import('./pages/recomendar').then(m => m.Recomendar) },
      { path: 'recomendar/:sid', loadComponent: () => import('./pages/recomendar').then(m => m.Recomendar) },
      { path: 'solicitudes', loadComponent: () => import('./pages/solicitudes').then(m => m.Solicitudes) },
      { path: 'avisos', canActivate: [rolGuardia('operador', 'gerencia')], loadComponent: () => import('./pages/avisos').then(m => m.Avisos) },
      { path: 'pendientes', canActivate: [rolGuardia('operador', 'gerencia')], loadComponent: () => import('./pages/pendientes').then(m => m.Pendientes) },
      { path: 'proveedores', canActivate: [rolGuardia('operador', 'gerencia')], loadComponent: () => import('./pages/proveedores').then(m => m.Proveedores) },
      { path: 'proveedores/:id', canActivate: [rolGuardia('operador', 'gerencia')], loadComponent: () => import('./pages/proveedores').then(m => m.Proveedores) },
      { path: 'seguimiento', loadComponent: () => import('./pages/seguimiento').then(m => m.Seguimiento) },
      { path: 'acerca', loadComponent: () => import('./pages/acerca').then(m => m.Acerca) },
      { path: 'panel', canActivate: [rolGuardia('operador', 'gerencia')], loadComponent: () => import('./pages/panel').then(m => m.Panel) },
    ],
  },
  { path: '**', redirectTo: '' },
];
