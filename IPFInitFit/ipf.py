import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler, PolynomialFeatures
from sklearn.decomposition import PCA

class IPF:
    def __init__(self):
        self.constraints = None  # Initialize constraints attribute

    def adjust_weights(self, data, dimension, target):
        if isinstance(dimension, str):
            dimension = [dimension]

        target_df = pd.DataFrame(target).reset_index()
        target_df.columns = dimension + ['target']

        current_totals = data.groupby(dimension)['weight'].sum().reset_index()
        current_totals.columns = dimension + ['current_total']

        adjustment_factors_df = current_totals.merge(target_df, on=dimension, how='left')
        adjustment_factors_df['weight_adj'] = adjustment_factors_df['target'] / adjustment_factors_df['current_total']

        data = data.merge(adjustment_factors_df[dimension + ['weight_adj']], on=dimension, how='left')
        data['weight'] *= data['weight_adj'].fillna(1)
        data.drop(columns=['weight_adj'], inplace=True)

        return data

    def apply_weighting(self, data, constraints, infer_initial_weights=False, max_iter=100, tol=1e-6):
        self.constraints = constraints  # Store constraints in the object
        initial_weights = np.ones(len(data))

        if infer_initial_weights:
            scaler = MinMaxScaler()
            X = self.create_design_matrix(data)
            X_scaled = scaler.fit_transform(X)
            pca = PCA(n_components=1)
            X_pca = pca.fit_transform(X_scaled)
            data['weight'] = initial_weights + X_pca.flatten()
        else:
            data['weight'] = initial_weights

        for _ in range(max_iter):
            old_weights = data['weight'].copy()
            for dimension, target in constraints:
                data = self.adjust_weights(data, dimension, target)

            if np.sum(np.abs(data['weight'] - old_weights)) < tol:
                break

        return data

    def create_design_matrix(self, data):
        X_columns = set()
        interaction_terms = []

        # Identify columns and interaction terms
        for dimension, _ in self.constraints:
            if isinstance(dimension, list):
                interaction_terms.append(dimension)
            else:
                X_columns.add(dimension)
        
        # Create dummy variables for single-dimensional constraints
        X = pd.get_dummies(data[list(X_columns)], drop_first=False).astype(int)
        
        # Create interaction terms for multi-dimensional constraints
        for term in interaction_terms:
            # Create dummy variables for the interaction terms
            interaction_df = pd.get_dummies(data[term], drop_first=False).astype(int)
            
            # Generate interaction terms using PolynomialFeatures
            poly = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
            interaction_matrix = poly.fit_transform(interaction_df)
            
            # Generate names for interaction terms
            feature_names = poly.get_feature_names_out(interaction_df.columns)
            interaction_df = pd.DataFrame(interaction_matrix, columns=feature_names)
            
            # Ensure that interaction_df has the same number of rows as X
            interaction_df.index = X.index
            
            # Remove interaction terms within the same dimension
            valid_columns = []
            for col in interaction_df.columns:
                dims_in_col = col.split(' ')
                dims_set = set(d.split('_')[0] for d in dims_in_col)
                if len(dims_set) > 1:
                    valid_columns.append(col)
            
            interaction_df = interaction_df[valid_columns]
            
            # Concatenate the interaction terms with the dummy variables
            X = pd.concat([X, interaction_df], axis=1)
        
        return X

    def check_results(self, data_clean, data_weighted, constraints):
        print("\nComparison of totals:")
        total_target_sum = 0
        total_diff = 0

        for dimension, target in constraints:
            before_total = data_clean.groupby(dimension).size()
            after_total = data_weighted.groupby(dimension)['weight'].sum()

            print(f"\nDimension: {dimension}")
            comparison = pd.DataFrame({
                'Before': before_total,
                'Target': target,
                'After': after_total
            })
            comparison['Diff (After - Target)'] = comparison['After'] - comparison['Target']
            comparison['% Diff'] = (comparison['Diff (After - Target)'] / comparison['Target']) * 100

            print(comparison)

            total_diff += np.sum(np.abs(comparison['Diff (After - Target)']))
            total_target_sum += np.sum(target)

        print(f"\nTotal absolute difference: {total_diff}")
        print(f"Average percentage difference: {total_diff / total_target_sum * 100:.4f}%")


