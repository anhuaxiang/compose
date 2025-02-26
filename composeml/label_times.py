import json
import os

import pandas as pd

from composeml.label_plots import LabelPlots


def read_csv(path, filename='label_times.csv', load_settings=True):
    """Read label times in csv format from disk.

    Args:
        path (str) : Directory on disk to read from.
        filename (str) : Filename for label times. Default value is `label_times.csv`.
        load_settings (bool) : Whether to load the settings used to make the label times.

    Returns:
        LabelTimes : Deserialized label times.
    """
    file = os.path.join(path, filename)
    assert os.path.exists(file), "data not found: '%s'" % file

    data = pd.read_csv(file, index_col='id')
    label_times = LabelTimes(data=data)

    if load_settings:
        label_times = label_times._load_settings(path)

    return label_times


def read_parquet(path, filename='label_times.parquet', load_settings=True):
    """Read label times in parquet format from disk.

    Args:
        path (str) : Directory on disk to read from.
        filename (str) : Filename for label times. Default value is `label_times.parquet`.
        load_settings (bool) : Whether to load the settings used to make the label times.

    Returns:
        LabelTimes : Deserialized label times.
    """
    file = os.path.join(path, filename)
    assert os.path.exists(file), "data not found: '%s'" % file

    data = pd.read_parquet(file)
    label_times = LabelTimes(data=data)

    if load_settings:
        label_times = label_times._load_settings(path)

    return label_times


def read_pickle(path, filename='label_times.pickle', load_settings=True):
    """Read label times in parquet format from disk.

    Args:
        path (str) : Directory on disk to read from.
        filename (str) : Filename for label times. Default value is `label_times.parquet`.
        load_settings (bool) : Whether to load the settings used to make the label times.

    Returns:
        LabelTimes : Deserialized label times.
    """
    file = os.path.join(path, filename)
    assert os.path.exists(file), "data not found: '%s'" % file

    data = pd.read_pickle(file)
    label_times = LabelTimes(data=data)

    if load_settings:
        label_times = label_times._load_settings(path)

    return label_times


class LabelTimes(pd.DataFrame):
    """A data frame containing labels made by a label maker.

    Attributes:
        settings
    """
    _metadata = ['settings']

    def __init__(self, data=None, target_entity=None, name=None, label_type=None, settings=None, *args, **kwargs):
        super().__init__(data=data, *args, **kwargs)

        if label_type is not None:
            error = 'label type must be "continuous" or "discrete"'
            assert label_type in ['continuous', 'discrete'], error

        self.settings = settings or {
            'target_entity': target_entity,
            'labeling_function': name,
            'label_type': label_type,
            'transforms': [],
        }

        self.plot = LabelPlots(self)

    def __finalize__(self, other, method=None, **kwargs):
        """Propagate metadata from other label times.

        Args:
            other (LabelTimes) : The label times from which to get the attributes from.
            method (str) : A passed method name for optionally taking different types of propagation actions based on this value.
        """
        if method == 'concat':
            other = other.objs[0]

            for key in self._metadata:
                value = getattr(other, key, None)
                setattr(self, key, value)

            return self

        return super().__finalize__(other=other, method=method, **kwargs)

    @property
    def _constructor(self):
        return LabelTimes

    @property
    def name(self):
        """Get name of label times."""
        return self.settings.get('labeling_function')

    @name.setter
    def name(self, value):
        """Set name of label times."""
        self.settings['labeling_function'] = value

    @property
    def target_entity(self):
        """Get target entity of label times."""
        return self.settings.get('target_entity')

    @target_entity.setter
    def target_entity(self, value):
        """Set target entity of label times."""
        self.settings['target_entity'] = value

    @property
    def label_type(self):
        """Get label type."""
        return self.settings.get('label_type')

    @label_type.setter
    def label_type(self, value):
        """Set label type."""
        self.settings['label_type'] = value

    @property
    def transforms(self):
        """Get transforms of label times."""
        return self.settings.get('transforms', [])

    @transforms.setter
    def transforms(self, value):
        """Set transforms of label times."""
        self.settings['transforms'] = value

    @property
    def is_discrete(self):
        """Whether labels are discrete."""
        if self.label_type is None:
            self.label_type = self.infer_type()

        return self.label_type == 'discrete'

    @property
    def distribution(self):
        """Returns label distribution if labels are discrete."""
        if self.is_discrete:
            labels = self.assign(count=1)
            labels = labels.groupby(self.name)
            distribution = labels['count'].count()
            return distribution

    @property
    def count(self):
        """Returns label count per instance."""
        count = self.groupby(self.target_entity)
        count = count[self.name].count()
        count = count.to_frame('count')
        return count

    @property
    def count_by_time(self):
        """Returns label count across cutoff times."""
        if self.is_discrete:
            keys = ['cutoff_time', self.name]
            value = self.groupby(keys).cutoff_time.count()
            value = value.unstack(self.name).fillna(0)
            value = value.cumsum()
            return value

        value = self.groupby('cutoff_time')
        value = value[self.name].count()
        value = value.cumsum()
        return value

    def describe(self):
        """Prints out label info with transform settings that reproduce labels."""
        if self.name is not None and self.is_discrete:
            print('Label Distribution\n' + '-' * 18, end='\n')
            distribution = self[self.name].value_counts()
            distribution.index = distribution.index.astype('str')
            distribution.sort_index(inplace=True)
            distribution['Total:'] = distribution.sum()
            print(distribution.to_string(), end='\n\n\n')

        settings = pd.Series(self.settings)
        transforms = settings.pop('transforms')

        print('Settings\n' + '-' * 8, end='\n')

        if settings.isnull().all():
            print('No settings', end='\n\n\n')
        else:
            settings.sort_index(inplace=True)
            print(settings.to_string(), end='\n\n\n')

        print('Transforms\n' + '-' * 10, end='\n')

        for step, transform in enumerate(transforms):
            transform = pd.Series(transform)
            transform.sort_index(inplace=True)
            name = transform.pop('transform')
            transform = transform.add_prefix('  - ')
            transform = transform.add_suffix(':')
            transform = transform.to_string()
            header = '{}. {}\n'.format(step + 1, name)
            print(header + transform, end='\n\n')

        if len(transforms) == 0:
            print('No transforms applied', end='\n\n')

    def copy(self):
        """
        Makes a copy of this object.

        Returns:
            LabelTimes : Copy of label times.
        """
        label_times = super().copy()
        label_times.settings = self.settings.copy()
        label_times.transforms = self.transforms.copy()
        return label_times

    def threshold(self, value, inplace=False):
        """
        Creates binary labels by testing if labels are above threshold.

        Args:
            value (float) : Value of threshold.
            inplace (bool) : Modify labels in place.

        Returns:
            labels (LabelTimes) : Instance of labels.
        """
        labels = self if inplace else self.copy()
        labels[self.name] = labels[self.name].gt(value)

        labels.label_type = 'discrete'
        labels.settings['label_type'] = 'discrete'

        transform = {'transform': 'threshold', 'value': value}
        labels.transforms.append(transform)

        if not inplace:
            return labels

    def apply_lead(self, value, inplace=False):
        """
        Shifts the label times earlier for predicting in advance.

        Args:
            value (str) : Time to shift earlier.
            inplace (bool) : Modify labels in place.

        Returns:
            labels (LabelTimes) : Instance of labels.
        """
        labels = self if inplace else self.copy()
        labels['cutoff_time'] = labels['cutoff_time'].sub(pd.Timedelta(value))

        transform = {'transform': 'apply_lead', 'value': value}
        labels.transforms.append(transform)

        if not inplace:
            return labels

    def bin(self, bins, quantiles=False, labels=None, right=True):
        """
        Bin labels into discrete intervals.

        Args:
            bins (int or array) : The criteria to bin by.

                * bins (int) : Number of bins either equal-width or quantile-based.
                    If `quantiles` is `False`, defines the number of equal-width bins.
                    The range is extended by .1% on each side to include the minimum and maximum values.
                    If `quantiles` is `True`, defines the number of quantiles (e.g. 10 for deciles, 4 for quartiles, etc.)
                * bins (array) : Bin edges either user defined or quantile-based.
                    If `quantiles` is `False`, defines the bin edges allowing for non-uniform width. No extension is done.
                    If `quantiles` is `True`, defines the bin edges usings an array of quantiles (e.g. [0, .25, .5, .75, 1.] for quartiles)

            quantiles (bool) : Determines whether to use a quantile-based discretization function.
            labels (array) : Specifies the labels for the returned bins. Must be the same length as the resulting bins.
            right (bool) : Indicates whether bins includes the rightmost edge or not. Does not apply to quantile-based bins.

        Returns:
            LabelTimes : Instance of labels.

        Examples:
            .. _equal-widths:

            Using bins of `equal-widths`_:

            >>> labels.bin(2).head(2).T
            label_id                                0                    1
            customer_id                             1                    1
            cutoff_time           2014-01-01 00:45:00  2014-01-01 00:48:00
            my_labeling_function      (157.5, 283.46]      (31.288, 157.5]

            .. _custom-widths:

            Using bins of `custom-widths`_:

            >>> values = labels.bin([0, 200, 400])
            >>> values.head(2).T
            label_id                                0                    1
            customer_id                             1                    1
            cutoff_time           2014-01-01 00:45:00  2014-01-01 00:48:00
            my_labeling_function           (200, 400]             (0, 200]

            .. _quantile-based:

            Using `quantile-based`_ bins:

            >>> values = labels.bin(4, quantiles=True) # (i.e. quartiles)
            >>> values.head(2).T
            label_id                                0                    1
            customer_id                             1                    1
            cutoff_time           2014-01-01 00:45:00  2014-01-01 00:48:00
            my_labeling_function    (137.44, 241.062]     (43.848, 137.44]

            .. _labels:

            Assigning `labels`_ to bins:

            >>> values = labels.bin(3, labels=['low', 'medium', 'high'])
            >>> values.head(2).T
            label_id                                0                    1
            customer_id                             1                    1
            cutoff_time           2014-01-01 00:45:00  2014-01-01 00:48:00
            my_labeling_function                 high                  low
        """ # noqa
        label_times = self.copy()
        values = label_times[self.name].values

        if quantiles:
            label_times[self.name] = pd.qcut(values, q=bins, labels=labels)

        else:
            label_times[self.name] = pd.cut(values, bins=bins, labels=labels, right=right)

        transform = {
            'transform': 'bin',
            'bins': bins,
            'quantiles': quantiles,
            'labels': labels,
            'right': right,
        }

        label_times.transforms.append(transform)
        label_times.label_type = 'discrete'
        return label_times

    def sample(self, n=None, frac=None, random_state=None, replace=False):
        """
        Return a random sample of labels.

        Args:
            n (int or dict) : Sample number of labels. A dictionary returns
                the number of samples to each label. Cannot be used with frac.
            frac (float or dict) : Sample fraction of labels. A dictionary returns
                the sample fraction to each label. Cannot be used with n.
            random_state (int) : Seed for the random number generator.
            replace (bool) : Sample with or without replacement. Default value is False.

        Returns:
            LabelTimes : Random sample of labels.

        Examples:

            Create mock data:

            >>> labels = {'labels': list('AABBBAA')}
            >>> labels = LabelTimes(labels, name='labels')
            >>> labels
              labels
            0      A
            1      A
            2      B
            3      B
            4      B
            5      A
            6      A

            Sample number of labels:

            >>> labels.sample(n=3, random_state=0).sort_index()
              labels
            1      A
            2      B
            6      A

            Sample number per label:

            >>> n_per_label = {'A': 1, 'B': 2}
            >>> labels.sample(n=n_per_label, random_state=0).sort_index()
              labels
            3      B
            4      B
            5      A

            Sample fraction of labels:

            >>> labels.sample(frac=.4, random_state=2).sort_index()
              labels
            1      A
            3      B
            4      B

            Sample fraction per label:

            >>> frac_per_label = {'A': .5, 'B': .34}
            >>> labels.sample(frac=frac_per_label, random_state=2).sort_index()
              labels
            4      B
            5      A
            6      A
        """ # noqa
        if isinstance(n, int):
            sample = super().sample(n=n, random_state=random_state, replace=replace)
            return sample

        if isinstance(n, dict):
            sample_per_label = []
            for label, n, in n.items():
                label = self[self[self.name] == label]
                sample = label.sample(n=n, random_state=random_state, replace=replace)
                sample_per_label.append(sample)

            sample = pd.concat(sample_per_label, axis=0, sort=False)
            return sample

        if isinstance(frac, float):
            sample = super().sample(frac=frac, random_state=random_state, replace=replace)
            return sample

        if isinstance(frac, dict):
            sample_per_label = []
            for label, frac, in frac.items():
                label = self[self[self.name] == label]
                sample = label.sample(frac=frac, random_state=random_state, replace=replace)
                sample_per_label.append(sample)

            sample = pd.concat(sample_per_label, axis=0, sort=False)
            return sample

    def infer_type(self):
        """Infer label type.

        Returns:
            str : Inferred label type. Either "continuous" or "discrete".
        """
        dtype = self[self.name].dtype
        is_discrete = pd.api.types.is_bool_dtype(dtype)
        is_discrete = is_discrete or pd.api.types.is_categorical_dtype(dtype)
        is_discrete = is_discrete or pd.api.types.is_object_dtype(dtype)

        if is_discrete:
            return 'discrete'

        return 'continuous'

    def equals(self, other):
        """Determines if two label time objects are the same.

        Args:
            other (LabelTimes) : Other label time object for comparison.

        Returns:
            bool : Whether label time objects are the same.
        """
        return super().equals(other) and self.settings == other.settings

    def _load_settings(self, path):
        """Read the settings in json format from disk.

        Args:
            path (str) : Directory on disk to read from.
        """
        file = os.path.join(path, 'settings.json')
        assert os.path.exists(file), 'settings not found'

        with open(file, 'r') as file:
            settings = json.load(file)

        if 'dtypes' in settings:
            dtypes = settings.pop('dtypes')
            self = LabelTimes(self.astype(dtypes))

        self.settings.update(settings)

        return self

    def _save_settings(self, path):
        """Write the settings in json format to disk.

        Args:
            path (str) : Directory on disk to write to.
        """
        dtypes = self.dtypes.astype('str')
        self.settings['dtypes'] = dtypes.to_dict()

        file = os.path.join(path, 'settings.json')
        with open(file, 'w') as file:
            json.dump(self.settings, file)
            del self.settings['dtypes']

    def to_csv(self, path, filename='label_times.csv', save_settings=True):
        """Write label times in csv format to disk.

        Args:
            path (str) : Location on disk to write to (will be created as a directory).
            filename (str) : Filename for label times. Default value is `label_times.csv`.
            save_settings (bool) : Whether to save the settings used to make the label times.
        """
        os.makedirs(path, exist_ok=True)
        file = os.path.join(path, filename)
        super().to_csv(file)

        if save_settings:
            self._save_settings(path)

    def to_parquet(self, path, filename='label_times.parquet', save_settings=True):
        """Write label times in parquet format to disk.

        Args:
            path (str) : Location on disk to write to (will be created as a directory).
            filename (str) : Filename for label times. Default value is `label_times.parquet`.
            save_settings (bool) : Whether to save the settings used to make the label times.
        """
        os.makedirs(path, exist_ok=True)
        file = os.path.join(path, filename)
        super().to_parquet(file, compression=None, engine='auto')

        if save_settings:
            self._save_settings(path)

    def to_pickle(self, path, filename='label_times.pickle', save_settings=True):
        """Write label times in pickle format to disk.

        Args:
            path (str) : Location on disk to write to (will be created as a directory).
            filename (str) : Filename for label times. Default value is `label_times.pickle`.
            save_settings (bool) : Whether to save the settings used to make the label times.
        """
        os.makedirs(path, exist_ok=True)
        file = os.path.join(path, filename)
        super().to_pickle(file)

        if save_settings:
            self._save_settings(path)
