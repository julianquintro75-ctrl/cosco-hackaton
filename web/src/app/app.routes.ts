import { Routes } from '@angular/router';
import { guardia } from './core/auth';

export const routes: Routes = [
  { path: 'login', title: 'Login', loadComponent: () => import('./pages/login').then(m => m.Login) },
  {
    path: '', canActivate: [guardia], loadComponent: () => import('./layout/shell').then(m => m.Shell),
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'recomendar' },
      { path: 'recomendar', loadComponent: () => import('./pages/recomendar').then(m => m.Recomendar) },
      { path: 'recomendar/:sid', loadComponent: () => import('./pages/recomendar').then(m => m.Recomendar) },
      { path: 'pendientes', loadComponent: () => import('./pages/pendientes').then(m => m.Pendientes) },
      { path: 'proveedores', loadComponent: () => import('./pages/proveedores').then(m => m.Proveedores) },
      { path: 'proveedores/:id', loadComponent: () => import('./pages/proveedores').then(m => m.Proveedores) },
      { path: 'panel', loadComponent: () => import('./pages/panel').then(m => m.Panel) },
    ],
  },
  { path: '**', redirectTo: '' },
];
