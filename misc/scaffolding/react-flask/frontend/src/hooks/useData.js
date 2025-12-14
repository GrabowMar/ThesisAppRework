// Custom Hooks - Reusable stateful logic
// Hooks for data fetching, form handling, and shared state
import { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';

// ============================================================================
// DATA FETCHING HOOKS - Implement custom hooks here
// ============================================================================
//
// Example custom hooks:
//
// /**
//  * Generic data fetching hook with loading and error states
//  */
// export function useData(fetchFn, dependencies = []) {
//   const [data, setData] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//
//   const refetch = useCallback(async () => {
//     setLoading(true);
//     setError(null);
//     try {
//       const response = await fetchFn();
//       setData(response.data);
//     } catch (err) {
//       setError(err.response?.data?.error || err.message);
//       toast.error('Failed to load data');
//     } finally {
//       setLoading(false);
//     }
//   }, [fetchFn]);
//
//   useEffect(() => {
//     refetch();
//   }, dependencies);
//
//   return { data, loading, error, refetch, setData };
// }
//
// /**
//  * Form handling hook with validation
//  */
// export function useForm(initialValues, validate) {
//   const [values, setValues] = useState(initialValues);
//   const [errors, setErrors] = useState({});
//   const [submitting, setSubmitting] = useState(false);
//
//   const handleChange = (e) => {
//     const { name, value, type, checked } = e.target;
//     setValues(prev => ({
//       ...prev,
//       [name]: type === 'checkbox' ? checked : value
//     }));
//   };
//
//   const handleSubmit = async (onSubmit) => {
//     if (validate) {
//       const validationErrors = validate(values);
//       if (Object.keys(validationErrors).length > 0) {
//         setErrors(validationErrors);
//         return;
//       }
//     }
//     setSubmitting(true);
//     try {
//       await onSubmit(values);
//       setValues(initialValues);
//     } finally {
//       setSubmitting(false);
//     }
//   };
//
//   return { values, errors, submitting, handleChange, handleSubmit, setValues };
// }
//
// IMPLEMENT YOUR CUSTOM HOOKS BELOW:
// ============================================================================

