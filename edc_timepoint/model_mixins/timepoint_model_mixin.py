import arrow

from django.apps import apps as django_apps
from django.db import models

from ..choices import TIMEPOINT_STATUS
from ..constants import OPEN_TIMEPOINT, CLOSED_TIMEPOINT, FEEDBACK
from ..timepoint import TimepointClosed
from ..timepoint_collection import TimepointConfigError

app_config = django_apps.get_app_config('edc_timepoint')


class UnableToCloseTimepoint(Exception):
    pass


class TimepointModelMixin(models.Model):

    """Makes a model serve as a marker for a timepoint, e.g. Appointment.
    """

    enabled_as_timepoint = True

    timepoint_status = models.CharField(
        max_length=15,
        choices=TIMEPOINT_STATUS,
        default=OPEN_TIMEPOINT)

    timepoint_opened_datetime = models.DateTimeField(
        null=True,
        editable=False,
        help_text="the original calculated model's datetime, updated in the signal")

    timepoint_closed_datetime = models.DateTimeField(
        null=True,
        editable=False)

    def save(self, *args, **kwargs):
        if self.enabled_as_timepoint:
            if (kwargs.get('update_fields') != ['timepoint_status'] and kwargs.
                    get('update_fields') != ['timepoint_opened_datetime', 'timepoint_status'] and kwargs.
                    get('update_fields') != ['timepoint_closed_datetime', 'timepoint_status']):
                self.timepoint_open_or_raise()
        super().save(*args, **kwargs)

    def timepoint_open_or_raise(self, timepoint=None):
        if not timepoint:
            try:
                timepoint = app_config.timepoints.get(self._meta.label_lower)
            except KeyError:
                raise TimepointConfigError(
                    f'Model \'{self._meta.label_lower}\' is not registered '
                    f'in AppConfig as a timepoint. '
                    f'See AppConfig for \'edc_timepoint\'.')
        if getattr(self, timepoint.status_field) != timepoint.closed_status:
            self.timepoint_status = OPEN_TIMEPOINT
            self.timepoint_closed_datetime = None
        elif self.timepoint_status == CLOSED_TIMEPOINT:
            raise TimepointClosed(
                f'This \'{self._meta.verbose_name}\' instance is closed '
                f'for data entry. See Timpoint.')
        return True

    def timepoint_close_timepoint(self):
        """Closes a timepoint.

        Updates the timepoint specific fields when the status field
        changes to closed.
        """
        timepoint = app_config.timepoints.get(self._meta.label_lower)
        status = getattr(self, timepoint.status_field)
        if status == timepoint.closed_status:
            self.timepoint_status = CLOSED_TIMEPOINT
            self.timepoint_closed_datetime = arrow.utcnow().datetime
            self.save(update_fields=['timepoint_status'])
        else:
            raise UnableToCloseTimepoint(
                f'Unable to close timepoint. Got {self._meta.label_lower}.'
                f'{timepoint.status_field} != {timepoint.closed_status}. '
                f'Got \'{status}\'.')

    def timepoint_open_timepoint(self):
        """Re-opens a timepoint.
        """
        if self.timepoint_status == CLOSED_TIMEPOINT:
            self.timepoint_status = OPEN_TIMEPOINT
            self.timepoint_closed_datetime = None
            self.save(
                update_fields=['timepoint_closed_datetime', 'timepoint_status'])

    def timepoint(self):
        """Formats and returns the status for the change_list.
        """
        if self.timepoint_status == OPEN_TIMEPOINT:
            return '<span style="color:green;">Open</span>'
        elif self.timepoint_status == CLOSED_TIMEPOINT:
            return '<span style="color:red;">Closed</span>'
        elif self.timepoint_status == FEEDBACK:
            return '<span style="color:orange;">Feedback</span>'
    # timepoint.allow_tags = True

    class Meta:
        abstract = True
